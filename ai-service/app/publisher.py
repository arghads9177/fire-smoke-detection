"""Posts detection events and heartbeats to the backend (API-key header),
through a small in-memory retry queue so a backend restart doesn't lose
detections (plan §3.2 Resilience).

Until the backend exists (plan day 6), every send simply fails over to the
console log + retry queue — no code change needed when it comes up.
"""

import logging
import threading
from collections import deque
from datetime import datetime, timezone

import httpx

from shared.schemas import DetectionEvent, DetectionSettings, Heartbeat

log = logging.getLogger("publisher")

REQUEST_TIMEOUT_S = 5.0
RETRY_INTERVAL_S = 2.0
QUEUE_MAXLEN = 1000  # bounded: oldest events drop first if the backend stays down


class Publisher:
    """Background sender owning all HTTP to the backend.

    Workers call publish()/heartbeat() (non-blocking); one daemon thread drains
    the event queue in order and sends the freshest heartbeat per camera.
    4xx responses are dropped as poison; connection errors and 5xx retry.
    """

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-API-Key": api_key}
        self._events: deque[DetectionEvent] = deque(maxlen=QUEUE_MAXLEN)
        self._statuses: dict[str, bool] = {}  # camera id -> online, freshest wins
        self._heartbeats_due: set[str] = set()
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="publisher", daemon=True)
        self._client = httpx.Client(timeout=REQUEST_TIMEOUT_S, headers=self._headers)

    # -- worker-facing (non-blocking) ------------------------------------

    def publish(self, event: DetectionEvent) -> None:
        with self._lock:
            if len(self._events) == self._events.maxlen:
                log.warning("event queue full, dropping oldest event")
            self._events.append(event)
        self._wakeup.set()

    def heartbeat(self, camera_id: str, online: bool) -> None:
        with self._lock:
            self._statuses[camera_id] = online
            self._heartbeats_due.add(camera_id)
        self._wakeup.set()

    # -- startup fetches (synchronous, with graceful fallback) ------------

    def fetch_settings(self) -> DetectionSettings | None:
        """GET /settings; None (caller falls back to defaults) if unreachable."""
        try:
            resp = self._client.get(f"{self._base_url}/settings")
            resp.raise_for_status()
            return DetectionSettings.model_validate(resp.json())
        except Exception as exc:
            log.warning("could not fetch settings from backend (%s) — using defaults", exc)
            return None

    def fetch_cameras(self) -> list[dict] | None:
        """GET /cameras; None (caller falls back to config.yaml) if unreachable/empty."""
        try:
            resp = self._client.get(f"{self._base_url}/cameras")
            resp.raise_for_status()
            cameras = resp.json()
            return cameras or None
        except Exception as exc:
            log.warning("could not fetch cameras from backend (%s) — using config.yaml", exc)
            return None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wakeup.set()
        self._thread.join(timeout=REQUEST_TIMEOUT_S + 1)
        self._client.close()

    # -- sender loop ---------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wakeup.wait(timeout=1.0)
            self._wakeup.clear()
            self._send_due_heartbeats()
            self._drain_events()

    def _send_due_heartbeats(self) -> None:
        with self._lock:
            due = {cam: self._statuses[cam] for cam in self._heartbeats_due}
            self._heartbeats_due.clear()
        for camera_id, online in due.items():
            body = Heartbeat(
                status="ONLINE" if online else "OFFLINE",
                timestamp=datetime.now(timezone.utc),
            )
            try:
                resp = self._client.post(
                    f"{self._base_url}/cameras/{camera_id}/heartbeat",
                    json=body.model_dump(mode="json"),
                )
                resp.raise_for_status()
            except Exception as exc:
                # Heartbeats are ephemeral: log and move on, never queue
                log.debug("heartbeat for %s failed: %s", camera_id, exc)

    def _drain_events(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                if not self._events:
                    return
                event = self._events.popleft()
            if not self._send_event(event):
                with self._lock:
                    self._events.appendleft(event)  # preserve order for retry
                # Backend down: wait, then let the outer loop retry
                self._stop.wait(RETRY_INTERVAL_S)
                return

    def _send_event(self, event: DetectionEvent) -> bool:
        """True if delivered or unrecoverable (4xx); False to retry."""
        try:
            resp = self._client.post(
                f"{self._base_url}/detections", json=event.model_dump(mode="json")
            )
            if 400 <= resp.status_code < 500:
                log.error(
                    "backend rejected event (%d): %s — dropping", resp.status_code, resp.text
                )
                return True
            resp.raise_for_status()
            log.info(
                "event delivered: %s %s %s conf=%.2f",
                event.cameraId, event.type, event.status, event.confidence,
            )
            return True
        except Exception as exc:
            log.warning(
                "event POST failed (%s): %s %s — will retry",
                exc, event.cameraId, event.type,
            )
            return False
