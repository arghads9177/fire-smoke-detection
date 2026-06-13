# Incident history schemas (plan §3.3 `incidents` collection).

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from shared.schemas import DetectionType


class IncidentOut(BaseModel):
    incidentId: str
    cameraId: str
    type: DetectionType
    level: Literal["CRITICAL", "WARNING"]
    confidence: float
    snapshot: str | None = None
    snapshotUrl: str | None = None
    timestamp: datetime
    acknowledged: bool


class IncidentListResponse(BaseModel):
    items: list[IncidentOut]
    total: int
    page: int
    pageSize: int
