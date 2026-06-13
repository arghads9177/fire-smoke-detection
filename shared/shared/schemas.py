"""The detection-event contract between ai-service and backend.

This is the frozen Day-3 schema from plan §7: the AI service serializes these
models into POST bodies and the backend validates requests against the very
same classes. Field names are camelCase because they double as the wire format
and the MongoDB document shape (plan §3.3).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DetectionType = Literal["FIRE", "SMOKE"]


class BoundingBox(BaseModel):
    """One detected region in pixel coordinates (x1, y1) top-left, (x2, y2) bottom-right."""

    label: DetectionType
    confidence: float = Field(ge=0.0, le=1.0)
    x1: float
    y1: float
    x2: float
    y2: float


class DetectionEvent(BaseModel):
    """A confirmed (debounced) detection, or the clearing of one.

    POST /api/v1/detections. `status="DETECTED"` carries the max confidence over
    the debounce window and a snapshot filename; `status="CLEARED"` is sent once
    the condition has been absent for the configured number of frames and has no
    snapshot.
    """

    cameraId: str
    type: DetectionType
    status: Literal["DETECTED", "CLEARED"] = "DETECTED"
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime
    snapshot: str | None = None  # filename under the shared snapshots dir
    boxes: list[BoundingBox] = []  # boxes of the triggering frame (empty for CLEARED)


class Heartbeat(BaseModel):
    """POST /api/v1/cameras/{cameraId}/heartbeat, sent every ~10 s per camera."""

    status: Literal["ONLINE", "OFFLINE"]
    timestamp: datetime


class DetectionSettings(BaseModel):
    """Runtime-tunable thresholds — the single `settings` document (plan §4).

    Owned by the backend (GET/PUT /api/v1/settings); the AI service fetches it
    at startup and falls back to these defaults if the backend is unreachable.
    """

    fireThreshold: float = Field(default=0.80, gt=0.0, lt=1.0)
    smokeThreshold: float = Field(default=0.75, gt=0.0, lt=1.0)
    debounceFrames: int = Field(default=3, ge=1)
    cooldownSeconds: float = Field(default=60.0, ge=0.0)
