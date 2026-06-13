# Socket.IO event emitters (plan §3.3): camera:status, alert:new,
# alert:updated, alert:cleared, incident:created.

from datetime import datetime
from typing import Any

import socketio

from app.config import get_settings

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=get_settings().cors_origin)


def _json_safe(value: Any) -> Any:
    """Recursively convert datetimes to ISO-8601 strings for Socket.IO payloads."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


async def emit_camera_status(camera: dict) -> None:
    await sio.emit("camera:status", _json_safe(camera))


async def emit_alert_new(alert: dict) -> None:
    await sio.emit("alert:new", _json_safe(alert))


async def emit_alert_updated(alert: dict) -> None:
    await sio.emit("alert:updated", _json_safe(alert))


async def emit_alert_cleared(alert: dict) -> None:
    await sio.emit("alert:cleared", _json_safe(alert))


async def emit_incident_created(incident: dict) -> None:
    await sio.emit("incident:created", _json_safe(incident))
