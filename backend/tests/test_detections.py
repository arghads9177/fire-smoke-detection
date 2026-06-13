# Alert engine via POST /detections (plan §3.3): thresholds, dedup
# (one active alert per camera+type), incident creation, camera state.

FIRE_EVENT = {
    "cameraId": "cam1",
    "type": "FIRE",
    "status": "DETECTED",
    "confidence": 0.9,
    "timestamp": "2026-06-13T00:00:00Z",
    "snapshot": "cam1_20260613000000.jpg",
    "boxes": [],
}


def test_detections_requires_api_key(client):
    resp = client.post("/api/v1/detections", json=FIRE_EVENT)
    assert resp.status_code == 401


def test_fire_detection_creates_incident_and_critical_alert(client, auth_headers):
    resp = client.post("/api/v1/detections", json=FIRE_EVENT, headers=auth_headers)
    assert resp.status_code == 202

    incidents = client.get("/api/v1/incidents").json()
    assert incidents["total"] == 1
    incident = incidents["items"][0]
    assert incident["cameraId"] == "cam1"
    assert incident["type"] == "FIRE"
    assert incident["level"] == "CRITICAL"
    assert incident["snapshotUrl"] == "/snapshots/cam1_20260613000000.jpg"

    alerts = client.get("/api/v1/alerts").json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["status"] == "ACTIVE"
    assert alert["level"] == "CRITICAL"
    assert alert["maxConfidence"] == 0.9
    assert alert["incidentId"] == incident["incidentId"]

    camera = client.get("/api/v1/cameras/cam1").json()
    assert camera["currentState"]["fire"] is True
    assert camera["currentState"]["confidence"] == 0.9


def test_repeated_detection_updates_alert_without_duplicating(client, auth_headers):
    client.post("/api/v1/detections", json=FIRE_EVENT, headers=auth_headers)
    second = {**FIRE_EVENT, "confidence": 0.95, "timestamp": "2026-06-13T00:01:00Z"}
    client.post("/api/v1/detections", json=second, headers=auth_headers)

    alerts = client.get("/api/v1/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["maxConfidence"] == 0.95
    assert alerts[0]["lastSeenAt"] == "2026-06-13T00:01:00"

    # one incident per DETECTED event for history, but a single active alert
    assert client.get("/api/v1/incidents").json()["total"] == 2


def test_below_threshold_is_ignored(client, auth_headers):
    weak_event = {**FIRE_EVENT, "confidence": 0.5}
    resp = client.post("/api/v1/detections", json=weak_event, headers=auth_headers)
    assert resp.status_code == 202

    assert client.get("/api/v1/incidents").json()["total"] == 0
    assert client.get("/api/v1/alerts").json() == []


def test_smoke_detection_creates_warning_alert(client, auth_headers):
    smoke_event = {**FIRE_EVENT, "type": "SMOKE", "confidence": 0.8}
    client.post("/api/v1/detections", json=smoke_event, headers=auth_headers)

    alerts = client.get("/api/v1/alerts").json()
    assert alerts[0]["type"] == "SMOKE"
    assert alerts[0]["level"] == "WARNING"


def test_cleared_event_marks_alert_cleared(client, auth_headers):
    client.post("/api/v1/detections", json=FIRE_EVENT, headers=auth_headers)
    cleared = {
        "cameraId": "cam1",
        "type": "FIRE",
        "status": "CLEARED",
        "confidence": 0.0,
        "timestamp": "2026-06-13T00:05:00Z",
    }
    client.post("/api/v1/detections", json=cleared, headers=auth_headers)

    alerts = client.get("/api/v1/alerts").json()
    assert alerts[0]["status"] == "CLEARED"

    camera = client.get("/api/v1/cameras/cam1").json()
    assert camera["currentState"]["fire"] is False


def test_cleared_with_no_active_alert_is_noop(client, auth_headers):
    cleared = {
        "cameraId": "cam1",
        "type": "FIRE",
        "status": "CLEARED",
        "confidence": 0.0,
        "timestamp": "2026-06-13T00:05:00Z",
    }
    resp = client.post("/api/v1/detections", json=cleared, headers=auth_headers)
    assert resp.status_code == 202
    assert client.get("/api/v1/alerts").json() == []


def test_alerts_filterable_by_status_and_camera(client, auth_headers):
    client.post("/api/v1/detections", json=FIRE_EVENT, headers=auth_headers)
    other = {**FIRE_EVENT, "cameraId": "cam2", "type": "SMOKE", "confidence": 0.8}
    client.post("/api/v1/detections", json=other, headers=auth_headers)

    assert len(client.get("/api/v1/alerts", params={"cameraId": "cam1"}).json()) == 1
    assert len(client.get("/api/v1/alerts", params={"status": "ACTIVE"}).json()) == 2
    assert len(client.get("/api/v1/alerts", params={"cameraId": "cam2"}).json()) == 1


def test_acknowledge_alert(client, auth_headers):
    client.post("/api/v1/detections", json=FIRE_EVENT, headers=auth_headers)
    alert_id = client.get("/api/v1/alerts").json()[0]["alertId"]

    resp = client.put(f"/api/v1/alerts/{alert_id}/acknowledge")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACKNOWLEDGED"

    # idempotent: acknowledging again keeps it ACKNOWLEDGED
    resp = client.put(f"/api/v1/alerts/{alert_id}/acknowledge")
    assert resp.json()["status"] == "ACKNOWLEDGED"


def test_acknowledge_unknown_alert_404(client):
    resp = client.put("/api/v1/alerts/does-not-exist/acknowledge")
    assert resp.status_code == 404
