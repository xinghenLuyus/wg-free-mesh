from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def test_auth_setup_login_and_protected_route(client: TestClient) -> None:
    state = client.get("/api/v1/auth/state")
    assert state.status_code == 200
    assert state.json()["data"]["setup_required"] is True

    setup = client.post("/api/v1/auth/setup", json={"password": TEST_PASSWORD, "locale": "zh-CN"})
    assert setup.status_code == 200
    token = setup.json()["data"]["access_token"]

    protected = client.get("/api/v1/configs")
    assert protected.status_code == 401

    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert login.status_code == 200

    authorized = client.get("/api/v1/configs", headers={"Authorization": f"Bearer {token}"})
    assert authorized.status_code == 200
    assert authorized.json()["success"] is True


def test_dev_reset_bootstrap_clears_only_auth_state(authenticated_client: TestClient) -> None:
    created = authenticated_client.post("/api/v1/configs", json={"name": "reset_keeps_config"})
    assert created.status_code == 200

    reset = authenticated_client.post("/api/v0/dev/reset-bootstrap")
    assert reset.status_code == 200
    assert reset.json()["data"]["auth_state"]["setup_required"] is True

    setup = authenticated_client.post("/api/v1/auth/setup", json={"password": TEST_PASSWORD, "locale": "zh-CN"})
    assert setup.status_code == 200
    token = setup.json()["data"]["access_token"]
    configs = authenticated_client.get("/api/v1/configs", headers={"Authorization": f"Bearer {token}"})
    assert configs.status_code == 200
    assert [item["name"] for item in configs.json()["data"]] == ["reset_keeps_config"]

