import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.services.client_update_service import client_update_service
from app.services.download_tools_service import download_tools_service


def test_update_check_does_not_build(monkeypatch):
    monkeypatch.setattr(download_tools_service, "build_client_artifact", lambda *args: pytest.fail("check must not build"))
    result = client_update_service.check("linux", "arm64")
    assert result["version"] == settings.app_version
    assert result["goos"] == "linux"


def test_github_update_is_pinned_without_building(monkeypatch):
    monkeypatch.setattr(download_tools_service, "build_client_artifact", lambda *args: pytest.fail("GitHub must not build"))
    result = client_update_service.artifact("github_release", "darwin", "arm64", settings.app_version, "node")
    assert f"/v{settings.app_version}/" in result["download_url"]
    assert result["checksum_url"] == result["download_url"] + ".sha256"
    with pytest.raises(AppError) as exc:
        client_update_service.artifact("local_build", "linux", "amd64", "0.0.0", "node")
    assert exc.value.code == "CLIENT_UPDATE_VERSION_CHANGED"


def test_update_requires_binding_credentials(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_mqtt_services", True)
    payload = {"config_id": "missing", "node_id": "missing", "goos": "linux", "goarch": "amd64"}
    assert client.post("/api/client/v1/update/check", json=payload).status_code == 401
    response = client.post("/api/client/v1/update/check", json=payload, auth=("missing", "wrong"))
    assert response.status_code == 401
