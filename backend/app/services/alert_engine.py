# Alert engine + incident service (plan §3.3): threshold rules, dedup
# (one active alert per camera+type), incident creation, Socket.IO emits.
#
# Mirrors the AI service's debounce/cooldown decision (alert_logic.py) as a
# server-side check, then turns each confirmed DetectionEvent into an
# incident record plus an active-alert upsert (or clears the active alert).

import uuid

from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.schemas import DetectionEvent, DetectionSettings

from app.db import strip_id
from app.sockets import (
    emit_alert_cleared,
    emit_alert_new,
    emit_alert_updated,
    emit_camera_status,
    emit_incident_created,
)

LEVELS = {"FIRE": "CRITICAL", "SMOKE": "WARNING"}

DEFAULT_CAMERA_STATE = {"fire": False, "smoke": False, "confidence": 0.0, "lastEventAt": None}


async def _get_settings(db: AsyncIOMotorDatabase) -> DetectionSettings:
    doc = await db.settings.find_one({})
    if doc is None:
        return DetectionSettings()
    return DetectionSettings.model_validate(strip_id(doc))


async def process_detection(db: AsyncIOMotorDatabase, event: DetectionEvent) -> None:
    """Apply the alert engine to one (debounced) detection event from the AI service."""
    if event.status == "DETECTED":
        await _handle_detected(db, event)
    else:
        await _handle_cleared(db, event)
    await _update_camera_state(db, event)


async def _handle_detected(db: AsyncIOMotorDatabase, event: DetectionEvent) -> None:
    settings = await _get_settings(db)
    threshold = settings.fireThreshold if event.type == "FIRE" else settings.smokeThreshold
    if event.confidence <= threshold:
        # Server-side validation (defense in depth): below threshold, ignore.
        return

    level = LEVELS[event.type]
    incident = {
        "incidentId": str(uuid.uuid4()),
        "cameraId": event.cameraId,
        "type": event.type,
        "level": level,
        "confidence": event.confidence,
        "snapshot": event.snapshot,
        "timestamp": event.timestamp,
        "acknowledged": False,
    }
    await db.incidents.insert_one(dict(incident))
    await emit_incident_created(incident)

    existing = await db.alerts.find_one(
        {
            "cameraId": event.cameraId,
            "type": event.type,
            "status": {"$in": ["ACTIVE", "ACKNOWLEDGED"]},
        }
    )
    if existing:
        await db.alerts.update_one(
            {"alertId": existing["alertId"]},
            {
                "$set": {
                    "lastSeenAt": event.timestamp,
                    "maxConfidence": max(existing["maxConfidence"], event.confidence),
                    "incidentId": incident["incidentId"],
                }
            },
        )
        updated = await db.alerts.find_one({"alertId": existing["alertId"]})
        await emit_alert_updated(strip_id(updated))
    else:
        alert = {
            "alertId": str(uuid.uuid4()),
            "cameraId": event.cameraId,
            "type": event.type,
            "level": level,
            "status": "ACTIVE",
            "firstSeenAt": event.timestamp,
            "lastSeenAt": event.timestamp,
            "maxConfidence": event.confidence,
            "incidentId": incident["incidentId"],
        }
        await db.alerts.insert_one(dict(alert))
        await emit_alert_new(alert)


async def _handle_cleared(db: AsyncIOMotorDatabase, event: DetectionEvent) -> None:
    existing = await db.alerts.find_one(
        {
            "cameraId": event.cameraId,
            "type": event.type,
            "status": {"$in": ["ACTIVE", "ACKNOWLEDGED"]},
        }
    )
    if existing is None:
        return
    await db.alerts.update_one(
        {"alertId": existing["alertId"]},
        {"$set": {"status": "CLEARED", "lastSeenAt": event.timestamp}},
    )
    updated = await db.alerts.find_one({"alertId": existing["alertId"]})
    await emit_alert_cleared(strip_id(updated))


async def _update_camera_state(db: AsyncIOMotorDatabase, event: DetectionEvent) -> None:
    field = event.type.lower()  # "fire" | "smoke"
    await db.cameras.update_one(
        {"cameraId": event.cameraId},
        {
            "$set": {
                f"currentState.{field}": event.status == "DETECTED",
                "currentState.confidence": event.confidence,
                "currentState.lastEventAt": event.timestamp,
            },
            "$setOnInsert": {
                "cameraId": event.cameraId,
                "name": event.cameraId,
                "location": "",
                "streamUrl": "",
                "status": "OFFLINE",
            },
        },
        upsert=True,
    )
    camera = await db.cameras.find_one({"cameraId": event.cameraId})
    await emit_camera_status(strip_id(camera))
