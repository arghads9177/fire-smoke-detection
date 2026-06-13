"""Annotated snapshot capture: draws bounding boxes + confidence on the
triggering frame and writes {cameraId}_{timestamp}.jpg to the shared
snapshots directory; the event payload carries the filename (plan §3.2).
"""

from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from shared.schemas import BoundingBox

# BGR: red for fire, slate gray for smoke
_COLORS = {"FIRE": (0, 0, 255), "SMOKE": (160, 160, 120)}


def annotate(frame: np.ndarray, boxes: list[BoundingBox]) -> np.ndarray:
    """Boxes + "fire 0.92"-style labels drawn on a copy of the frame."""
    out = frame.copy()
    for box in boxes:
        color = _COLORS[box.label]
        p1 = (int(box.x1), int(box.y1))
        p2 = (int(box.x2), int(box.y2))
        cv2.rectangle(out, p1, p2, color, 2)
        label = f"{box.label.lower()} {box.confidence:.2f}"
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        ty = max(p1[1], th + baseline)  # keep the label inside the image at the top edge
        cv2.rectangle(out, (p1[0], ty - th - baseline), (p1[0] + tw, ty), color, -1)
        cv2.putText(
            out, label, (p1[0], ty - baseline // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA,
        )
    return out


def save_snapshot(
    frame: np.ndarray,
    boxes: list[BoundingBox],
    camera_id: str,
    directory: Path,
    timestamp: datetime | None = None,
) -> str:
    """Write the annotated JPEG and return its filename (the event payload field)."""
    timestamp = timestamp or datetime.now(timezone.utc)
    # Millisecond suffix so fire+smoke confirmed in the same second don't collide
    filename = f"{camera_id}_{timestamp.strftime('%Y%m%dT%H%M%S')}{timestamp.microsecond // 1000:03d}.jpg"
    directory.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(directory / filename), annotate(frame, boxes))
    return filename
