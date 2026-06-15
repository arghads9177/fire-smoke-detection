# GET/POST/PUT/DELETE /cameras + POST /cameras/{id}/heartbeat (plan §3.3).

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.schemas import Heartbeat

from app.config import get_settings
from app.db import get_db, strip_id
from app.dependencies import require_api_key
from app.schemas.cameras import CameraCreate, CameraOut, CameraUpdate, StreamUrlUpdate
from app.services.alert_engine import DEFAULT_CAMERA_STATE
from app.sockets import emit_camera_status

router = APIRouter(prefix="/cameras", tags=["cameras"])

ALLOWED_FEED_EXTENSIONS = {".mp4"}
ALLOWED_STREAM_SCHEMES = ("rtsp://", "rtmp://", "http://", "https://")


@router.get("", response_model=list[CameraOut])
async def list_cameras(db: AsyncIOMotorDatabase = Depends(get_db)) -> list[dict]:
    cameras = await db.cameras.find().to_list(length=None)
    return [strip_id(c) for c in cameras]


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
async def create_camera(
    body: CameraCreate, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    if await db.cameras.find_one({"cameraId": body.cameraId}):
        raise HTTPException(status.HTTP_409_CONFLICT, "camera already exists")
    doc = {
        **body.model_dump(),
        "status": "OFFLINE",
        "lastHeartbeat": None,
        "currentState": dict(DEFAULT_CAMERA_STATE),
    }
    await db.cameras.insert_one(dict(doc))
    return doc


@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(camera_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    camera = await db.cameras.find_one({"cameraId": camera_id})
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "camera not found")
    return strip_id(camera)


@router.put("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: str, body: CameraUpdate, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    changes = body.model_dump(exclude_unset=True)
    if changes:
        result = await db.cameras.update_one({"cameraId": camera_id}, {"$set": changes})
        if result.matched_count == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "camera not found")
    camera = await db.cameras.find_one({"cameraId": camera_id})
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "camera not found")
    return strip_id(camera)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(camera_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> None:
    result = await db.cameras.delete_one({"cameraId": camera_id})
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "camera not found")


@router.post("/{camera_id}/feed", response_model=CameraOut)
async def upload_feed(
    camera_id: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Replace a camera's stream source with a manually uploaded .mp4 file.

    The AI service polls /cameras and hot-swaps its capture source to the
    saved file's absolute path, so the upload is picked up without a restart.
    """
    camera = await db.cameras.find_one({"cameraId": camera_id})
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "camera not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_FEED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "only .mp4 files are supported")

    camera_uploads_dir = Path(get_settings().uploads_dir).resolve() / camera_id
    camera_uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = camera_uploads_dir / f"{uuid.uuid4().hex}{suffix}"
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    await db.cameras.update_one({"cameraId": camera_id}, {"$set": {"streamUrl": str(dest)}})
    camera = await db.cameras.find_one({"cameraId": camera_id})
    await emit_camera_status(strip_id(camera))
    return strip_id(camera)


@router.post("/{camera_id}/stream", response_model=CameraOut)
async def set_stream_url(
    camera_id: str,
    body: StreamUrlUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Point a camera at a new stream source (e.g. a phone publishing to MediaMTX).

    The AI service picks up the change on its next /cameras poll
    (_refresh_stream_urls), so no restart is needed.
    """
    camera = await db.cameras.find_one({"cameraId": camera_id})
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "camera not found")

    if not body.streamUrl.startswith(ALLOWED_STREAM_SCHEMES):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported stream URL scheme")

    await db.cameras.update_one(
        {"cameraId": camera_id}, {"$set": {"streamUrl": body.streamUrl}}
    )
    camera = await db.cameras.find_one({"cameraId": camera_id})
    await emit_camera_status(strip_id(camera))
    return strip_id(camera)


@router.post(
    "/{camera_id}/heartbeat",
    dependencies=[Depends(require_api_key)],
)
async def heartbeat(
    camera_id: str, body: Heartbeat, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    await db.cameras.update_one(
        {"cameraId": camera_id},
        {
            "$set": {"status": body.status, "lastHeartbeat": body.timestamp},
            "$setOnInsert": {
                "cameraId": camera_id,
                "name": camera_id,
                "location": "",
                "streamUrl": "",
                "currentState": dict(DEFAULT_CAMERA_STATE),
            },
        },
        upsert=True,
    )
    camera = await db.cameras.find_one({"cameraId": camera_id})
    await emit_camera_status(strip_id(camera))
    return {"status": "ok"}
