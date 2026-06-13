# GET/PUT /settings (plan §3.3 + §4): the single detection-threshold doc,
# shared with the AI service via shared.schemas.DetectionSettings.

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.schemas import DetectionSettings

from app.db import get_db, strip_id
from app.schemas.settings import SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=DetectionSettings)
async def get_settings_doc(db: AsyncIOMotorDatabase = Depends(get_db)) -> DetectionSettings:
    doc = await db.settings.find_one({})
    if doc is None:
        return DetectionSettings()
    return DetectionSettings.model_validate(strip_id(doc))


@router.put("", response_model=DetectionSettings)
async def update_settings(
    body: SettingsUpdate, db: AsyncIOMotorDatabase = Depends(get_db)
) -> DetectionSettings:
    doc = await db.settings.find_one({})
    current = DetectionSettings.model_validate(strip_id(doc)) if doc else DetectionSettings()
    updated = current.model_copy(update=body.model_dump(exclude_unset=True))
    await db.settings.update_one({}, {"$set": updated.model_dump()}, upsert=True)
    return updated
