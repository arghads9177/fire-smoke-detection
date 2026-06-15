# Camera CRUD + status schemas (plan §3.3 `cameras` collection).

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CameraState(BaseModel):
    fire: bool = False
    smoke: bool = False
    confidence: float = 0.0
    lastEventAt: datetime | None = None


class CameraCreate(BaseModel):
    cameraId: str
    name: str
    location: str
    streamUrl: str


class CameraUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    streamUrl: str | None = None


class StreamUrlUpdate(BaseModel):
    streamUrl: str


class CameraOut(BaseModel):
    cameraId: str
    name: str
    location: str
    streamUrl: str
    status: Literal["ONLINE", "OFFLINE"] = "OFFLINE"
    lastHeartbeat: datetime | None = None
    currentState: CameraState = CameraState()
