from fastapi.testclient import TestClient

from app.core.config import settings


def test_mqtt_settings_update_and_reset(authenticated_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_mqtt_services", True)
    initial = authenticated_client.get("/api/v1/settings/mqtt")
    assert initial.status_code == 200
    assert initial.json()["data"] == {"host": "localhost", "port": 1883, "tls": False}

    updated = authenticated_client.put(
        "/api/v1/settings/mqtt",
        json={"host": "broker.example.test", "port": 8883, "tls": True},
    )
    assert updated.status_code == 200
    assert updated.json()["data"] == {"host": "broker.example.test", "port": 8883, "tls": True}

    reset = authenticated_client.post("/api/v1/settings/mqtt/reset")
    assert reset.status_code == 200
    assert reset.json()["data"] == {"host": "localhost", "port": 1883, "tls": False}


def test_mqtt_settings_reject_when_deployment_disables_mqtt(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/settings/mqtt")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MQTT_DISABLED"


def test_ui_settings_persist(authenticated_client: TestClient) -> None:
    updated = authenticated_client.put("/api/v1/settings/ui", json={"locale": "en-US", "theme_mode": "dark"})
    assert updated.status_code == 200
    assert updated.json()["data"] == {"locale": "en-US", "theme_mode": "dark"}

    loaded = authenticated_client.get("/api/v1/settings/ui")
    assert loaded.status_code == 200
    assert loaded.json()["data"] == {"locale": "en-US", "theme_mode": "dark"}
