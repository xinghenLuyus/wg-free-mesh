from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("WFM_DATABASE", "sqlite:///:memory:")
os.environ.setdefault("WFM_ENABLE_MQTT_SERVICES", "false")
os.environ.setdefault("WFM_ENABLE_DEV_TEST_API", "true")
os.environ.setdefault("WFM_DEBUG", "true")

TEST_PASSWORD = "test-password-123"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.chdir(tmp_path)
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("WFM_DATABASE", database_url)
    from app.core.config import settings
    from app.data.database import reset_engine
    from app.main import create_app

    settings.database = database_url
    reset_engine()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    reset_engine()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/setup", json={"password": TEST_PASSWORD, "locale": "zh-CN"})
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def authenticated_client(client: TestClient, auth_headers: dict[str, str]) -> TestClient:
    client.headers.update(auth_headers)
    return client
