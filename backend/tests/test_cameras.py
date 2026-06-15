import io

from app.config import get_settings

CAMERA = {
    "cameraId": "cam1",
    "name": "Loading Dock",
    "location": "Warehouse A",
    "streamUrl": "rtsp://localhost:8554/cam1",
}


def test_create_and_get_camera(client):
    resp = client.post("/api/v1/cameras", json=CAMERA)
    assert resp.status_code == 201
    body = resp.json()
    assert body["cameraId"] == "cam1"
    assert body["status"] == "OFFLINE"
    assert body["currentState"] == {
        "fire": False,
        "smoke": False,
        "confidence": 0.0,
        "lastEventAt": None,
    }

    resp = client.get("/api/v1/cameras/cam1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Loading Dock"


def test_create_duplicate_camera_conflicts(client):
    client.post("/api/v1/cameras", json=CAMERA)
    resp = client.post("/api/v1/cameras", json=CAMERA)
    assert resp.status_code == 409


def test_list_cameras(client):
    client.post("/api/v1/cameras", json=CAMERA)
    resp = client.get("/api/v1/cameras")
    assert resp.status_code == 200
    assert [c["cameraId"] for c in resp.json()] == ["cam1"]


def test_update_camera(client):
    client.post("/api/v1/cameras", json=CAMERA)
    resp = client.put("/api/v1/cameras/cam1", json={"name": "Dock A"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Dock A"
    assert resp.json()["location"] == "Warehouse A"  # unchanged


def test_update_unknown_camera_404(client):
    resp = client.put("/api/v1/cameras/cam99", json={"name": "x"})
    assert resp.status_code == 404


def test_delete_camera(client):
    client.post("/api/v1/cameras", json=CAMERA)
    resp = client.delete("/api/v1/cameras/cam1")
    assert resp.status_code == 204
    assert client.get("/api/v1/cameras/cam1").status_code == 404


def test_delete_unknown_camera_404(client):
    resp = client.delete("/api/v1/cameras/cam99")
    assert resp.status_code == 404


def test_heartbeat_requires_api_key(client):
    resp = client.post(
        "/api/v1/cameras/cam1/heartbeat",
        json={"status": "ONLINE", "timestamp": "2026-06-13T00:00:00Z"},
    )
    assert resp.status_code == 401


def test_upload_feed_replaces_stream_url(client, monkeypatch, tmp_path):
    client.post("/api/v1/cameras", json=CAMERA)
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))

    resp = client.post(
        "/api/v1/cameras/cam1/feed",
        files={"file": ("clip.mp4", io.BytesIO(b"fake-mp4-bytes"), "video/mp4")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["streamUrl"].startswith(str(tmp_path))
    assert body["streamUrl"].endswith(".mp4")

    camera = client.get("/api/v1/cameras/cam1").json()
    assert camera["streamUrl"] == body["streamUrl"]


def test_upload_feed_rejects_non_mp4(client):
    client.post("/api/v1/cameras", json=CAMERA)
    resp = client.post(
        "/api/v1/cameras/cam1/feed",
        files={"file": ("clip.avi", io.BytesIO(b"data"), "video/x-msvideo")},
    )
    assert resp.status_code == 400


def test_upload_feed_unknown_camera_404(client):
    resp = client.post(
        "/api/v1/cameras/cam99/feed",
        files={"file": ("clip.mp4", io.BytesIO(b"data"), "video/mp4")},
    )
    assert resp.status_code == 404


def test_set_stream_url_persists_and_emits(client, monkeypatch):
    client.post("/api/v1/cameras", json=CAMERA)

    emitted = []

    async def fake_emit(event, data):
        emitted.append((event, data))

    from app.sockets import sio

    monkeypatch.setattr(sio, "emit", fake_emit)

    resp = client.post(
        "/api/v1/cameras/cam1/stream",
        json={"streamUrl": "rtsp://localhost:8554/phonecam"},
    )
    assert resp.status_code == 200
    assert resp.json()["streamUrl"] == "rtsp://localhost:8554/phonecam"

    camera = client.get("/api/v1/cameras/cam1").json()
    assert camera["streamUrl"] == "rtsp://localhost:8554/phonecam"

    assert emitted == [("camera:status", emitted[0][1])]
    assert emitted[0][1]["streamUrl"] == "rtsp://localhost:8554/phonecam"


def test_set_stream_url_rejects_bad_scheme(client):
    client.post("/api/v1/cameras", json=CAMERA)
    resp = client.post(
        "/api/v1/cameras/cam1/stream",
        json={"streamUrl": "ftp://localhost/phonecam"},
    )
    assert resp.status_code == 400


def test_set_stream_url_unknown_camera_404(client):
    resp = client.post(
        "/api/v1/cameras/cam99/stream",
        json={"streamUrl": "rtsp://localhost:8554/phonecam"},
    )
    assert resp.status_code == 404


def test_heartbeat_upserts_and_sets_status(client, auth_headers):
    resp = client.post(
        "/api/v1/cameras/cam1/heartbeat",
        json={"status": "ONLINE", "timestamp": "2026-06-13T00:00:00Z"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    camera = client.get("/api/v1/cameras/cam1").json()
    assert camera["status"] == "ONLINE"
    assert camera["lastHeartbeat"] is not None
