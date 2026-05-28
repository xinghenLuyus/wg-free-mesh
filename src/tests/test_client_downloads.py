from __future__ import annotations

from fastapi.testclient import TestClient


def test_client_download_options_enable_github_release(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/tools/download/client-options")

    assert response.status_code == 200
    sources = {item["value"]: item for item in response.json()["data"]["sources"]}
    assert sources["github_release"]["available"] is True


def test_github_release_client_download_returns_direct_url(authenticated_client: TestClient, monkeypatch) -> None:
    from app.core.config import settings
    from app.services.download_tools_service import download_tools_service

    checked: dict[str, str] = {}

    def fake_check(url: str, version: str, filename: str) -> None:
        checked["url"] = url
        checked["version"] = version
        checked["filename"] = filename

    monkeypatch.setattr(download_tools_service, "_ensure_release_asset_exists", fake_check)

    response = authenticated_client.post(
        "/api/v1/tools/download/client-artifacts/build",
        json={"source": "github_release", "goos": "windows", "goarch": "amd64"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    expected_filename = f"wfm-client-windows-amd64-v{settings.app_version}.zip"
    assert data["filename"] == expected_filename
    assert data["download_url"] == checked["url"]
    assert data["download_url"].endswith(f"/releases/download/v{settings.app_version}/{expected_filename}")
    assert checked["version"] == settings.app_version
    assert checked["filename"] == expected_filename
