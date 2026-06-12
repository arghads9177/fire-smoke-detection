"""Posts detection events and heartbeats to the backend (API-key header),
through a small in-memory retry queue so a backend restart doesn't lose
detections (plan §3.2 Resilience).
"""
