"""Entrypoint: loads config, fetches settings/cameras from the backend,
and spawns one detection worker per camera (plan §3.2).

Run with: python -m app.main
"""

import logging
import signal
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from shared.schemas import DetectionEvent, DetectionSettings

from app.alert_logic import Action, build_states
from app.detector import Detector, max_confidence
from app.publisher import Publisher
from app.snapshot import save_snapshot
from app.stream_reader import StreamReader

SERVICE_ROOT = Path(__file__).resolve().parents[1]  # ai-service/
STATS_LOG_INTERVAL_S = 30.0

log = logging.getLogger("main")


class CameraWorker:
    """One thread per camera: sample frames -> detect -> alert logic -> publish."""

    def __init__(
        self,
        camera_id: str,
        stream_url: str,
        detector: Detector,
        settings: DetectionSettings,
        publisher: Publisher,
        snapshots_dir: Path,
        sample_fps: float,
    ):
        self.camera_id = camera_id
        self.stream_url = stream_url
        self.online = False
        self._detector = detector
        self._publisher = publisher
        self._snapshots_dir = snapshots_dir
        self._states = build_states(settings)
        self._log = logging.getLogger(f"worker.{camera_id}")
        self._reader = StreamReader(
            stream_url, sample_fps, on_status=self._on_stream_status, name=camera_id
        )
        self._thread = threading.Thread(target=self._run, name=f"worker-{camera_id}", daemon=True)
        # rolling stats for the structured fps/latency log line
        self._frames = 0
        self._latency_total = 0.0
        self._stats_since = time.monotonic()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._reader.stop()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def set_stream_url(self, url: str) -> None:
        """Hot-swap the capture source, e.g. when a .mp4 is uploaded for this
        camera via the dashboard (plan: manual mp4 feed)."""
        if url == self.stream_url:
            return
        self._log.info("stream source changed: %s -> %s", self.stream_url, url)
        self.stream_url = url
        self._reader.set_url(url)

    def _on_stream_status(self, online: bool) -> None:
        self.online = online
        # Push the transition immediately rather than waiting for the next 10 s tick
        self._publisher.heartbeat(self.camera_id, online)

    def _run(self) -> None:
        for frame in self._reader.frames():
            started = time.monotonic()
            boxes = self._detector.detect(frame)
            self._record_stats(time.monotonic() - started)

            now = time.monotonic()
            for detection_type, state in self._states.items():
                confidence = max_confidence(boxes, detection_type)
                action = state.update(confidence, now)
                if action is Action.RAISE:
                    self._raise_event(detection_type, state.episode_max_confidence, frame, boxes)
                elif action is Action.CLEAR:
                    self._clear_event(detection_type)
        self._log.info("worker stopped")

    def _raise_event(self, detection_type, confidence, frame, boxes) -> None:
        timestamp = datetime.now(timezone.utc)
        type_boxes = [b for b in boxes if b.label == detection_type]
        filename = save_snapshot(
            frame, type_boxes, self.camera_id, self._snapshots_dir, timestamp
        )
        self._log.warning(
            "%s confirmed (conf=%.2f) — snapshot %s", detection_type, confidence, filename
        )
        self._publisher.publish(
            DetectionEvent(
                cameraId=self.camera_id,
                type=detection_type,
                status="DETECTED",
                confidence=confidence,
                timestamp=timestamp,
                snapshot=filename,
                boxes=type_boxes,
            )
        )

    def _clear_event(self, detection_type) -> None:
        self._log.info("%s cleared", detection_type)
        self._publisher.publish(
            DetectionEvent(
                cameraId=self.camera_id,
                type=detection_type,
                status="CLEARED",
                confidence=0.0,
                timestamp=datetime.now(timezone.utc),
            )
        )

    def _record_stats(self, latency: float) -> None:
        self._frames += 1
        self._latency_total += latency
        elapsed = time.monotonic() - self._stats_since
        if elapsed >= STATS_LOG_INTERVAL_S:
            self._log.info(
                "fps=%.1f avg_inference_ms=%.0f",
                self._frames / elapsed,
                1000 * self._latency_total / self._frames,
            )
            self._frames = 0
            self._latency_total = 0.0
            self._stats_since = time.monotonic()


def _refresh_stream_urls(publisher: Publisher, workers_by_id: dict[str, CameraWorker]) -> None:
    """Picks up streamUrl changes (e.g. a manually uploaded .mp4) without a restart."""
    cameras = publisher.fetch_cameras()
    if not cameras:
        return
    for cam in cameras:
        worker = workers_by_id.get(cam["cameraId"])
        if worker is not None:
            worker.set_stream_url(cam["streamUrl"])


def load_config() -> dict:
    with open(SERVICE_ROOT / "config.yaml") as fh:
        return yaml.safe_load(fh)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    config = load_config()

    publisher = Publisher(
        base_url=config["backend"]["url"],
        api_key=config["backend"]["api_key"],
    )
    publisher.start()

    # Runtime-tunable thresholds come from the backend settings collection (plan §4);
    # shared-schema defaults apply when the backend isn't up yet.
    settings = publisher.fetch_settings() or DetectionSettings()
    log.info(
        "thresholds: fire>%.2f smoke>%.2f debounce=%d cooldown=%.0fs",
        settings.fireThreshold, settings.smokeThreshold,
        settings.debounceFrames, settings.cooldownSeconds,
    )

    cameras = publisher.fetch_cameras() or config["cameras"]
    log.info("cameras: %s", [c["cameraId"] for c in cameras])

    detector = Detector(
        model_path=str(SERVICE_ROOT / config["model"]["path"]),
        class_ids=config["model"]["classes"],
        image_size=config["inference"]["image_size"],
    )

    snapshots_dir = (SERVICE_ROOT / config["snapshots"]["dir"]).resolve()
    workers = [
        CameraWorker(
            camera_id=cam["cameraId"],
            stream_url=cam["streamUrl"],
            detector=detector,
            settings=settings,
            publisher=publisher,
            snapshots_dir=snapshots_dir,
            sample_fps=config["inference"]["fps"],
        )
        for cam in cameras
    ]
    for worker in workers:
        worker.start()

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    # Main thread doubles as the ~10 s heartbeat ticker (plan §3.2 step 5)
    heartbeat_interval = config["backend"]["heartbeat_seconds"]
    workers_by_id = {worker.camera_id: worker for worker in workers}
    while not stop.is_set():
        for worker in workers:
            publisher.heartbeat(worker.camera_id, worker.online)
        _refresh_stream_urls(publisher, workers_by_id)
        stop.wait(heartbeat_interval)

    log.info("shutting down")
    for worker in workers:
        worker.stop()
    for worker in workers:
        worker.join(timeout=5)
    for worker in workers:
        publisher.heartbeat(worker.camera_id, False)
    publisher.stop()


if __name__ == "__main__":
    main()
