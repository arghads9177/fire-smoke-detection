# Pydantic request/response models. The detection-event schema is the shared
# contract with the AI service — frozen on Day 3, lives in shared/shared/schemas.py,
# never forked. This package holds the backend-only schemas (cameras, alerts,
# incidents, settings).

from app.schemas.alerts import AlertOut
from app.schemas.cameras import CameraCreate, CameraOut, CameraState, CameraUpdate
from app.schemas.incidents import IncidentListResponse, IncidentOut
from app.schemas.settings import SettingsUpdate

__all__ = [
    "AlertOut",
    "CameraCreate",
    "CameraOut",
    "CameraState",
    "CameraUpdate",
    "IncidentListResponse",
    "IncidentOut",
    "SettingsUpdate",
]
