"""YOLO inference wrapper around the ultralytics API: loads the checkpoint
from config, runs on sampled frames, and filters results to the fire/smoke
classes. Designed so tests can stub the underlying model (plan §6).
"""

import threading

import numpy as np

from shared.schemas import BoundingBox, DetectionType

# Floor passed to the model so annotation boxes exist below the alert thresholds;
# the real thresholds are applied downstream in alert_logic (layered defense, §3.2).
MODEL_CONF_FLOOR = 0.25


class Detector:
    """Wraps an ultralytics YOLO model behind `detect(frame) -> list[BoundingBox]`.

    A single instance is shared by all camera workers; predict() is serialized
    with a lock because ultralytics models are not thread-safe (CPU inference
    is effectively serial anyway, plan §7).
    """

    def __init__(
        self,
        model_path: str,
        class_ids: dict[str, int],
        image_size: int = 640,
        model=None,
    ):
        if model is None:
            from ultralytics import YOLO  # deferred: heavy import, stubbed in tests

            model = YOLO(model_path)
        self._model = model
        self._image_size = image_size
        self._lock = threading.Lock()
        # config.yaml maps {"fire": 0, "smoke": 1}; invert to class id -> event type
        self._id_to_type: dict[int, DetectionType] = {
            class_id: name.upper()  # type: ignore[misc]
            for name, class_id in class_ids.items()
            if name.lower() in ("fire", "smoke")
        }

    def detect(self, frame: np.ndarray) -> list[BoundingBox]:
        with self._lock:
            result = self._model.predict(
                frame,
                imgsz=self._image_size,
                conf=MODEL_CONF_FLOOR,
                verbose=False,
            )[0]

        boxes: list[BoundingBox] = []
        for box in result.boxes or []:
            label = self._id_to_type.get(int(box.cls[0]))
            if label is None:
                continue
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            boxes.append(
                BoundingBox(
                    label=label,
                    confidence=float(box.conf[0]),
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
        return boxes


def max_confidence(boxes: list[BoundingBox], label: DetectionType) -> float:
    """Highest confidence for one type in a frame; 0.0 when absent."""
    return max((b.confidence for b in boxes if b.label == label), default=0.0)
