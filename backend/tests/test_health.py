def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_system_info_returns_lan_ip(client):
    resp = client.get("/api/v1/system/info")
    assert resp.status_code == 200
    assert "lanIp" in resp.json()
    assert resp.json()["lanIp"]
