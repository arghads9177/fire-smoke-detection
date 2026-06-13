# GET /incidents + GET /incidents/{id} (plan §3.3): paginated history with
# filters (camera, type, date range) and the snapshot URL for the modal.

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db, strip_id
from app.schemas.incidents import IncidentListResponse, IncidentOut

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _with_snapshot_url(incident: dict) -> dict:
    snapshot = incident.get("snapshot")
    incident["snapshotUrl"] = f"/snapshots/{snapshot}" if snapshot else None
    return incident


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    cameraId: str | None = Query(default=None),
    type: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IncidentListResponse:
    query: dict = {}
    if cameraId:
        query["cameraId"] = cameraId
    if type:
        query["type"] = type
    if start or end:
        ts_query: dict = {}
        if start:
            ts_query["$gte"] = start
        if end:
            ts_query["$lte"] = end
        query["timestamp"] = ts_query

    total = await db.incidents.count_documents(query)
    cursor = (
        db.incidents.find(query)
        .sort("timestamp", -1)
        .skip((page - 1) * pageSize)
        .limit(pageSize)
    )
    incidents = await cursor.to_list(length=pageSize)
    items = [_with_snapshot_url(strip_id(i)) for i in incidents]
    return IncidentListResponse(items=items, total=total, page=page, pageSize=pageSize)


@router.get("/{incident_id}", response_model=IncidentOut)
async def get_incident(incident_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    incident = await db.incidents.find_one({"incidentId": incident_id})
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "incident not found")
    return _with_snapshot_url(strip_id(incident))
