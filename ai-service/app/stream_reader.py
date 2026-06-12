"""RTSP frame capture: cv2.VideoCapture (FFMPEG backend, TCP transport),
latest-frame sampling (drop stale buffered frames), and reconnect with
exponential backoff (1 s -> 30 s cap). Repeated failures mark the camera
OFFLINE via heartbeat (plan §3.2 Resilience).
"""
