"""RTSP frame capture: cv2.VideoCapture (FFMPEG backend, TCP transport),
latest-frame sampling (drop stale buffered frames), and reconnect with
exponential backoff (1 s -> 30 s cap). Repeated failures mark the camera
OFFLINE via heartbeat (plan §3.2 Resilience).
"""

import logging
import os
import threading
import time
from collections.abc import Callable, Iterator

import numpy as np

# Must be set before the first VideoCapture FFMPEG open anywhere in the process.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2  # noqa: E402

BACKOFF_INITIAL_S = 1.0
BACKOFF_CAP_S = 30.0
# Consecutive grab() failures before tearing the capture down and reconnecting
# (a stalled/corrupted stream often fails reads without closing the socket).
MAX_GRAB_FAILURES = 30


class StreamReader:
    """Yields the freshest frame of one RTSP stream at the sampling FPS.

    grab() is called on every arriving frame so the decoder buffer never backs
    up; retrieve() (the expensive decode) runs only at sample times, so what we
    hand to the model reflects "now". `on_status(online)` fires on every
    connect/disconnect transition for ONLINE/OFFLINE heartbeat tracking.
    """

    def __init__(
        self,
        url: str,
        sample_fps: float = 3.0,
        on_status: Callable[[bool], None] | None = None,
        name: str | None = None,
    ):
        self.url = url
        self.sample_fps = sample_fps
        self.on_status = on_status or (lambda online: None)
        self._stop = threading.Event()
        self._url_changed = threading.Event()
        self._log = logging.getLogger(f"stream.{name or url}")

    def stop(self) -> None:
        self._stop.set()

    def set_url(self, url: str) -> None:
        """Switch the capture source (e.g. RTSP -> an uploaded mp4 file).

        Takes effect on the next grab(), forcing a reconnect against the new
        source instead of waiting for the current one to fail.
        """
        if url == self.url:
            return
        self.url = url
        self._url_changed.set()

    def frames(self) -> Iterator[np.ndarray]:
        """Generator of sampled frames; handles reconnection internally and
        only returns when stop() is called."""
        backoff = BACKOFF_INITIAL_S
        online = False
        while not self._stop.is_set():
            self._url_changed.clear()
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                if online:
                    online = False
                    self.on_status(False)
                self._log.warning("connect failed, retrying in %.0fs", backoff)
                if self._stop.wait(backoff):
                    break
                backoff = min(backoff * 2, BACKOFF_CAP_S)
                continue

            backoff = BACKOFF_INITIAL_S
            online = True
            self.on_status(True)
            self._log.info("connected")

            sample_interval = 1.0 / self.sample_fps
            next_sample = time.monotonic()
            grab_failures = 0
            while not self._stop.is_set():
                if self._url_changed.is_set():
                    self._log.info("stream source changed, reconnecting")
                    break
                if not cap.grab():
                    grab_failures += 1
                    if grab_failures >= MAX_GRAB_FAILURES:
                        self._log.warning(
                            "%d consecutive read failures, reconnecting", grab_failures
                        )
                        break
                    time.sleep(0.05)
                    continue
                grab_failures = 0

                now = time.monotonic()
                if now < next_sample:
                    continue
                ok, frame = cap.retrieve()
                if not ok or frame is None:
                    continue
                # Schedule from "now" so a stall doesn't cause a burst of samples
                next_sample = now + sample_interval
                yield frame

            cap.release()
            if self._stop.is_set():
                break
            online = False
            self.on_status(False)

        if online:
            self.on_status(False)
