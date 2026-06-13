def test_get_settings_defaults(client):
    resp = client.get("/api/v1/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "fireThreshold": 0.80,
        "smokeThreshold": 0.75,
        "debounceFrames": 3,
        "cooldownSeconds": 60.0,
    }


def test_put_settings_partial_update_persists(client):
    resp = client.put("/api/v1/settings", json={"fireThreshold": 0.9})
    assert resp.status_code == 200
    body = resp.json()
    assert body["fireThreshold"] == 0.9
    # untouched fields keep their defaults
    assert body["smokeThreshold"] == 0.75
    assert body["debounceFrames"] == 3

    resp = client.get("/api/v1/settings")
    assert resp.json()["fireThreshold"] == 0.9


def test_put_settings_rejects_out_of_range(client):
    resp = client.put("/api/v1/settings", json={"fireThreshold": 1.5})
    assert resp.status_code == 422
