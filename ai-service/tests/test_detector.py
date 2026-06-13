"""Detector wrapper tests with a stubbed ultralytics model (plan §6)."""

import numpy as np

from app.detector import MODEL_CONF_FLOOR, Detector, max_confidence
from shared.schemas import BoundingBox

CLASS_IDS = {"fire": 0, "smoke": 1}
FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


class FakeBox:
    """Mimics one element of ultralytics Results.boxes."""

    def __init__(self, cls, conf, xyxy):
        self.cls = np.array([cls])
        self.conf = np.array([conf])
        self.xyxy = np.array([xyxy])


class FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


class FakeModel:
    def __init__(self, boxes):
        self._boxes = boxes
        self.calls = []

    def predict(self, frame, **kwargs):
        self.calls.append(kwargs)
        return [FakeResult(self._boxes)]


def make_detector(boxes, class_ids=CLASS_IDS, **kwargs):
    return Detector("unused.pt", class_ids, model=FakeModel(boxes), **kwargs)


def test_maps_class_ids_to_event_types():
    detector = make_detector(
        [FakeBox(0, 0.92, [10, 20, 110, 220]), FakeBox(1, 0.81, [5, 5, 50, 50])]
    )
    boxes = detector.detect(FRAME)
    assert [b.label for b in boxes] == ["FIRE", "SMOKE"]
    fire = boxes[0]
    assert fire.confidence == 0.92
    assert (fire.x1, fire.y1, fire.x2, fire.y2) == (10, 20, 110, 220)


def test_filters_unknown_classes():
    # e.g. a checkpoint that also detects "person" (class 2)
    detector = make_detector([FakeBox(2, 0.99, [0, 0, 1, 1]), FakeBox(0, 0.9, [0, 0, 1, 1])])
    boxes = detector.detect(FRAME)
    assert [b.label for b in boxes] == ["FIRE"]


def test_empty_and_none_boxes():
    assert make_detector([]).detect(FRAME) == []
    assert make_detector(None).detect(FRAME) == []


def test_passes_image_size_and_conf_floor_to_model():
    model = FakeModel([])
    detector = Detector("unused.pt", CLASS_IDS, image_size=480, model=model)
    detector.detect(FRAME)
    assert model.calls[0]["imgsz"] == 480
    assert model.calls[0]["conf"] == MODEL_CONF_FLOOR
    assert model.calls[0]["verbose"] is False


def test_respects_config_class_id_remapping():
    # weights with swapped ids: config.yaml is the source of truth
    detector = make_detector([FakeBox(1, 0.9, [0, 0, 1, 1])], class_ids={"fire": 1, "smoke": 0})
    assert [b.label for b in detector.detect(FRAME)] == ["FIRE"]


def test_max_confidence_helper():
    boxes = [
        BoundingBox(label="FIRE", confidence=0.7, x1=0, y1=0, x2=1, y2=1),
        BoundingBox(label="FIRE", confidence=0.9, x1=0, y1=0, x2=1, y2=1),
        BoundingBox(label="SMOKE", confidence=0.8, x1=0, y1=0, x2=1, y2=1),
    ]
    assert max_confidence(boxes, "FIRE") == 0.9
    assert max_confidence(boxes, "SMOKE") == 0.8
    assert max_confidence([], "FIRE") == 0.0
