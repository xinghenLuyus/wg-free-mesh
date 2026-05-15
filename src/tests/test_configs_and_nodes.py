from fastapi.testclient import TestClient
from uuid import uuid4


def test_create_config_node_and_mesh_flow(authenticated_client: TestClient) -> None:
    config_name = f"mesh_test_{uuid4().hex[:8]}"
    config_response = authenticated_client.post(
        "/api/v1/configs",
        json={
            "name": config_name,
            "description": "api flow",
            "virtual_subnet": "10.88.0.0/24",
            "default_listen_port": 51830,
            "default_mtu": 1420,
            "default_dns": "1.1.1.1",
            "auto_sync": True,
            "enabled": True,
        },
    )
    assert config_response.status_code == 200
    config = config_response.json()["data"]
    assert config["name"] == config_name

    node_response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/nodes",
        json={
            "name": "edge-a",
            "ipv4_address": "198.51.100.10",
            "listen_port": 51831,
            "virtual_ip": "10.88.0.2/32",
            "node_type": "dynamic",
            "auto_sync": True,
            "tags": ["lab"],
        },
    )
    assert node_response.status_code == 200
    node = node_response.json()["data"]
    assert node["config_id"] == config["id"]
    assert node["node_type"] == "dynamic"

    sync_status = authenticated_client.get(f"/api/v1/configs/{config['id']}/nodes/{node['id']}/sync-status")
    assert sync_status.status_code == 200
    assert sync_status.json()["data"]["node_id"] == node["id"]


def test_unknown_config_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/configs/not-found")
    assert response.status_code == 428
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_SETUP_REQUIRED"


def test_unknown_config_returns_structured_error(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/configs/not-found")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFIG_NOT_FOUND"
