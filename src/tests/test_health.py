from fastapi.testclient import TestClient

from app.core.config import settings


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


def test_system_status_hides_update_when_no_new_release(authenticated_client: TestClient, monkeypatch) -> None:
    from app.services.update_check_service import system_update_check_service

    monkeypatch.setattr(system_update_check_service, "get_status", lambda: {"has_update": False})

    response = authenticated_client.get("/api/v1/system/status")

    assert response.status_code == 200
    assert response.json()["data"]["update"]["has_update"] is False


def test_update_candidate_rules_for_stable_and_rc_versions() -> None:
    from app.services.update_check_service import _is_update_candidate, _parse_version

    def version(value: str):
        parsed = _parse_version(value)
        assert parsed is not None
        return parsed

    stable = version("1.0.0")
    rc = version("1.0.0-rc.1")

    assert _is_update_candidate(stable, version("1.1.0"))
    assert not _is_update_candidate(stable, version("1.1.0-rc.1"))
    assert _is_update_candidate(rc, version("1.0.0"))
    assert _is_update_candidate(rc, version("1.0.0-rc.2"))
    assert _is_update_candidate(rc, version("1.1.0-rc.1"))
    assert not _is_update_candidate(rc, version("0.9.9"))


def test_public_source_guard_allows_main_host_without_origin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_dev_test_api", False)
    monkeypatch.setattr(settings, "public_origin", "https://wfm.example.com")

    response = client.get("/api/v1/system/health", headers={"host": "wfm.example.com"})

    assert response.status_code == 200


def test_public_source_guard_allows_extra_origin_only_through_main_host(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_dev_test_api", False)
    monkeypatch.setattr(settings, "public_origin", "https://wfm.example.com")
    monkeypatch.setattr(settings, "extra_allowed_origins", ["http://localhost:5173"])

    allowed = client.get(
        "/api/v1/system/health",
        headers={"host": "wfm.example.com", "origin": "http://localhost:5173"},
    )
    rejected = client.get(
        "/api/v1/system/health",
        headers={"host": "localhost:8000", "origin": "http://localhost:5173"},
    )

    assert allowed.status_code == 200
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "PUBLIC_HOST_REJECTED"


def test_public_source_guard_rejects_unknown_origin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_dev_test_api", False)
    monkeypatch.setattr(settings, "public_origin", "https://wfm.example.com")

    response = client.get(
        "/api/v1/system/health",
        headers={"host": "wfm.example.com", "origin": "https://other.example.com"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PUBLIC_ORIGIN_REJECTED"


def test_mqtt_public_host_uses_public_origin_host(monkeypatch) -> None:
    monkeypatch.setattr(settings, "public_origin", "https://wfm.example.com:8443")

    assert settings.mqtt_public_host == "wfm.example.com"
