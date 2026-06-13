# GET /alerts + PUT /alerts/{id}/acknowledge (plan §3.3).

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db, strip_id
from app.schemas.alerts import AlertOut
from app.sockets import emit_alert_updated

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    status: str | None = Query(default=None),
    cameraId: str | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[dict]:
    query: dict = {}
    if status:
        query["status"] = status
    if cameraId:
        query["cameraId"] = cameraId
    alerts = await db.alerts.find(query).sort("lastSeenAt", -1).to_list(length=None)
    return [strip_id(a) for a in alerts]


@router.put("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: str, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    alert = await db.alerts.find_one({"alertId": alert_id})
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
    if alert["status"] == "ACTIVE":
        await db.alerts.update_one({"alertId": alert_id}, {"$set": {"status": "ACKNOWLEDGED"}})
        alert = await db.alerts.find_one({"alertId": alert_id})
        await emit_alert_updated(strip_id(dict(alert)))
    return strip_id(alert)
