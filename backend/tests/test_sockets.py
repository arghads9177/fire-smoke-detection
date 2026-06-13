from datetime import datetime, timezone

from app.sockets import _json_safe


def test_json_safe_converts_datetime_to_iso_string():
    now = datetime(2026, 6, 13, 7, 56, 52, tzinfo=timezone.utc)
    payload = {
        "cameraId": "cam2",
        "lastHeartbeat": now,
        "currentState": {"fire": False, "lastEventAt": now},
        "history": [{"timestamp": now}, "unchanged"],
        "status": "ONLINE",
    }

    safe = _json_safe(payload)

    assert safe["lastHeartbeat"] == now.isoformat()
    assert safe["currentState"]["lastEventAt"] == now.isoformat()
    assert safe["history"][0]["timestamp"] == now.isoformat()
    assert safe["history"][1] == "unchanged"
    assert safe["status"] == "ONLINE"
