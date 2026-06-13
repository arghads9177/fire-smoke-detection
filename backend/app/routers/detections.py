# POST /detections (plan §3.3) — AI service posts raw, debounced detection
# events here (API-key protected); the alert engine decides whether it
# becomes/updates an active alert and incident.

from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.schemas import DetectionEvent

from app.db import get_db
from app.dependencies import require_api_key
from app.services.alert_engine import process_detection

router = APIRouter(tags=["detections"], dependencies=[Depends(require_api_key)])


@router.post("/detections", status_code=status.HTTP_202_ACCEPTED)
async def post_detection(
    event: DetectionEvent, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    await process_detection(db, event)
    return {"status": "accepted"}
