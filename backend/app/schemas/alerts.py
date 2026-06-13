# Active-alert schema (plan §3.3 `alerts` collection).

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from shared.schemas import DetectionType


class AlertOut(BaseModel):
    alertId: str
    cameraId: str
    type: DetectionType
    level: Literal["CRITICAL", "WARNING"]
    status: Literal["ACTIVE", "ACKNOWLEDGED", "CLEARED"]
    firstSeenAt: datetime
    lastSeenAt: datetime
    maxConfidence: float
    incidentId: str
