FIRE_EVENT = {
    "cameraId": "cam1",
    "type": "FIRE",
    "status": "DETECTED",
    "confidence": 0.9,
    "snapshot": "cam1_1.jpg",
    "boxes": [],
}


def _post(client, auth_headers, **overrides):
    event = {**FIRE_EVENT, **overrides}
    resp = client.post("/api/v1/detections", json=event, headers=auth_headers)
    assert resp.status_code == 202


def test_incidents_pagination(client, auth_headers):
    for i in range(5):
        _post(client, auth_headers, timestamp=f"2026-06-13T00:0{i}:00Z", snapshot=f"cam1_{i}.jpg")

    page1 = client.get("/api/v1/incidents", params={"page": 1, "pageSize": 2}).json()
    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    # newest first
    assert page1["items"][0]["timestamp"] == "2026-06-13T00:04:00"

    page3 = client.get("/api/v1/incidents", params={"page": 3, "pageSize": 2}).json()
    assert len(page3["items"]) == 1


def test_incidents_filter_by_camera_and_type(client, auth_headers):
    _post(client, auth_headers, timestamp="2026-06-13T00:00:00Z")
    _post(client, auth_headers, cameraId="cam2", type="SMOKE", confidence=0.8,
          timestamp="2026-06-13T00:01:00Z")

    cam1_only = client.get("/api/v1/incidents", params={"cameraId": "cam1"}).json()
    assert cam1_only["total"] == 1

    smoke_only = client.get("/api/v1/incidents", params={"type": "SMOKE"}).json()
    assert smoke_only["total"] == 1


def test_incidents_filter_by_date_range(client, auth_headers):
    _post(client, auth_headers, timestamp="2026-06-13T00:00:00Z")
    _post(client, auth_headers, timestamp="2026-06-14T00:00:00Z", snapshot="cam1_2.jpg")

    only_first_day = client.get(
        "/api/v1/incidents",
        params={"start": "2026-06-13T00:00:00Z", "end": "2026-06-13T23:59:59Z"},
    ).json()
    assert only_first_day["total"] == 1


def test_get_incident_detail(client, auth_headers):
    _post(client, auth_headers, timestamp="2026-06-13T00:00:00Z")
    incident_id = client.get("/api/v1/incidents").json()["items"][0]["incidentId"]

    resp = client.get(f"/api/v1/incidents/{incident_id}")
    assert resp.status_code == 200
    assert resp.json()["snapshotUrl"] == "/snapshots/cam1_1.jpg"


def test_get_unknown_incident_404(client):
    resp = client.get("/api/v1/incidents/does-not-exist")
    assert resp.status_code == 404
