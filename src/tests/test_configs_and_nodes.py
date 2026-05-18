from fastapi.testclient import TestClient
import httpx
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


def test_switching_config_to_awg_backfills_node_i_chain(authenticated_client: TestClient) -> None:
    config_name = f"mesh_awg_{uuid4().hex[:8]}"
    config_response = authenticated_client.post(
        "/api/v1/configs",
        json={
            "name": config_name,
            "description": "awg switch",
            "virtual_subnet": "10.89.0.0/24",
            "default_listen_port": 51840,
            "default_mtu": 1420,
            "default_dns": "1.1.1.1",
            "auto_sync": True,
            "enabled": True,
            "tunnel_protocol": "wireguard",
        },
    )
    assert config_response.status_code == 200
    config = config_response.json()["data"]

    node_response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/nodes",
        json={
            "name": "edge-awg",
            "ipv4_address": "198.51.100.11",
            "listen_port": 51841,
            "virtual_ip": "10.89.0.2/32",
            "node_type": "dynamic",
            "auto_sync": True,
        },
    )
    assert node_response.status_code == 200
    node = node_response.json()["data"]
    assert node["awg_i1"] is None

    update_response = authenticated_client.put(
        f"/api/v1/configs/{config['id']}",
        json={
            **config,
            "tunnel_protocol": "amneziawg_2",
        },
    )
    assert update_response.status_code == 200

    switched_node_response = authenticated_client.get(f"/api/v1/nodes/{node['id']}")
    assert switched_node_response.status_code == 200
    switched_node = switched_node_response.json()["data"]
    assert switched_node["awg_jc"] is not None
    assert switched_node["awg_jmax"] > switched_node["awg_jmin"]
    for key in ("awg_i1", "awg_i2", "awg_i3", "awg_i4", "awg_i5"):
        assert isinstance(switched_node[key], str)
        assert switched_node[key]


def test_reset_client_deletes_emqx_user_and_disconnects_client(authenticated_client: TestClient, monkeypatch) -> None:
    from app.core.config import settings
    import app.services.control_plane_service as control_plane_module

    config_response = authenticated_client.post(
        "/api/v1/configs",
        json={
            "name": f"mesh_reset_{uuid4().hex[:8]}",
            "description": "reset client",
            "virtual_subnet": "10.90.0.0/24",
            "default_listen_port": 51850,
            "default_mtu": 1420,
            "default_dns": "1.1.1.1",
            "auto_sync": True,
            "enabled": True,
        },
    )
    assert config_response.status_code == 200
    config = config_response.json()["data"]
    node_response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/nodes",
        json={
            "name": "edge-reset",
            "ipv4_address": "198.51.100.12",
            "listen_port": 51851,
            "virtual_ip": "10.90.0.2/32",
            "node_type": "dynamic",
            "auto_sync": True,
        },
    )
    assert node_response.status_code == 200
    node = node_response.json()["data"]
    calls: list[tuple[str, str]] = []

    class FakeEmqxService:
        def delete_node_user(self, *, node_id: str) -> httpx.Response:
            calls.append(("delete", node_id))
            return httpx.Response(204)

        def disconnect_node_client(self, *, node_id: str) -> httpx.Response:
            calls.append(("disconnect", node_id))
            return httpx.Response(204)

    monkeypatch.setattr(settings, "enable_mqtt_services", True)
    monkeypatch.setattr(control_plane_module, "emqx_service", FakeEmqxService())

    state = control_plane_module.control_plane_service.reset_client_state(config["id"], node["id"])

    assert calls == [("delete", node["id"]), ("disconnect", node["id"])]
    assert state["client_initialized"] is False
    assert state["mqtt_username"] == ""
    assert state["mqtt_client_id"] == ""


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
