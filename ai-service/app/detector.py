"""YOLO inference wrapper around the ultralytics API: loads the checkpoint
from config, runs on sampled frames, and filters results to the fire/smoke
classes. Designed so tests can stub the underlying model (plan §6).
"""
