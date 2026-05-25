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

    class FakeEmqxReconcileService:
        def revoke_node_user(self, *, node_id: str) -> dict[str, bool]:
            calls.append(("revoke", node_id))
            return {"deleted": True, "disconnected": True}

    monkeypatch.setattr(settings, "enable_mqtt_services", True)
    monkeypatch.setattr(control_plane_module, "emqx_reconcile_service", FakeEmqxReconcileService())

    state = control_plane_module.control_plane_service.reset_client_state(config["id"], node["id"])

    assert calls == [("revoke", node["id"])]
    assert state["client_initialized"] is False
    assert state["mqtt_username"] == ""
    assert state["mqtt_client_id"] == ""


def test_detect_ack_refreshes_client_version(authenticated_client: TestClient) -> None:
    from app.data.store import store

    config_response = authenticated_client.post(
        "/api/v1/configs",
        json={
            "name": f"mesh_detect_version_{uuid4().hex[:8]}",
            "description": "detect client version",
            "virtual_subnet": "10.91.0.0/24",
            "default_listen_port": 51860,
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
            "name": "edge-detect-version",
            "ipv4_address": "198.51.100.13",
            "listen_port": 51861,
            "virtual_ip": "10.91.0.2/32",
            "node_type": "dynamic",
            "auto_sync": True,
        },
    )
    assert node_response.status_code == 200
    node = node_response.json()["data"]

    store.mark_client_bound(
        config["id"],
        node["id"],
        username="u",
        client_id="c",
        password="p",
        platform="windows",
        version="0.2.2",
        hostname="host-a",
    )
    store.record_detect_ack(
        config["id"],
        node["id"],
        client_online=True,
        wg_online=False,
        platform="windows",
        client_version="0.2.3",
    )

    state = store.get_client_state(config["id"], node["id"])
    assert state["client_version"] == "0.2.3"
    assert state["client_version_label"] == "Windows 0.2.3"


def _create_quick_mesh_config(authenticated_client: TestClient, *, ipv6: bool = True) -> tuple[dict, list[dict]]:
    config_response = authenticated_client.post(
        "/api/v1/configs",
        json={
            "name": f"mesh_quick_{uuid4().hex[:8]}",
            "description": "quick mesh",
            "virtual_subnet": "10.92.0.0/24",
            "default_listen_port": 51870,
            "default_mtu": 1420,
            "default_dns": "1.1.1.1",
            "auto_sync": True,
            "enabled": True,
        },
    )
    assert config_response.status_code == 200
    config = config_response.json()["data"]
    nodes: list[dict] = []
    for index in range(3):
        node_response = authenticated_client.post(
            f"/api/v1/configs/{config['id']}/nodes",
            json={
                "name": f"edge-quick-{index + 1}",
                "ipv4_address": f"198.51.100.{20 + index}",
                "ipv6_address": f"2001:db8::{20 + index}" if ipv6 else None,
                "listen_port": 51870 + index,
                "virtual_ip": f"10.92.0.{index + 2}/32",
                "node_type": "dynamic",
                "auto_sync": True,
            },
        )
        assert node_response.status_code == 200
        nodes.append(node_response.json()["data"])
    return config, nodes


def test_quick_generate_hub_spoke_replaces_mesh_links(authenticated_client: TestClient) -> None:
    from app.data.store import store

    config, nodes = _create_quick_mesh_config(authenticated_client)
    store.create_peer_link_group(
        config["id"],
        {
            "forward": store.build_peer_link_draft(config["id"], nodes[1]["id"], nodes[2]["id"], "ipv4")["forward"],
            "reverse": store.build_peer_link_draft(config["id"], nodes[1]["id"], nodes[2]["id"], "ipv4")["reverse"],
        },
    )

    response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/mesh/quick-generate",
        json={"mode": "hub_spoke", "endpoint_ref_family": "ipv4", "hub_node_id": nodes[0]["id"], "use_preshared_key": True},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["generated_groups"] == 2
    assert data["deleted_links"] == 2
    links = store.list_peer_links(config["id"])
    assert len(links) == 4
    assert {link.local_node_id for link in links if link.direction == "forward"} == {nodes[0]["id"]}
    hub_to_branch = [link for link in links if link.local_node_id == nodes[0]["id"]]
    branch_to_hub = [link for link in links if link.peer_node_id == nodes[0]["id"]]
    assert {link.allowed_ips for link in hub_to_branch} == {nodes[1]["virtual_ip"], nodes[2]["virtual_ip"]}
    assert {link.allowed_ips for link in branch_to_hub} == {config["virtual_subnet"]}
    groups: dict[str, set[str | None]] = {}
    for link in links:
        groups.setdefault(link.link_group_id, set()).add(link.preshared_key)
    assert all(len(keys) == 1 and next(iter(keys)) for keys in groups.values())


def test_quick_generate_full_mesh_requires_public_address(authenticated_client: TestClient) -> None:
    config, nodes = _create_quick_mesh_config(authenticated_client, ipv6=False)

    response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/mesh/quick-generate",
        json={"mode": "full_mesh", "endpoint_ref_family": "ipv6", "hub_node_id": nodes[0]["id"]},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "QUICK_MESH_ENDPOINT_REQUIRED"
    assert len(body["error"]["detail"]["nodes"]) == 3


def test_quick_generate_full_mesh_creates_all_pairs(authenticated_client: TestClient) -> None:
    from app.data.store import store

    config, _nodes = _create_quick_mesh_config(authenticated_client)

    response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/mesh/quick-generate",
        json={"mode": "full_mesh", "endpoint_ref_family": "ipv4"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["generated_groups"] == 3
    assert len(store.list_peer_links(config["id"])) == 6


def test_quick_generate_free_mesh_routes_gateway_scopes(authenticated_client: TestClient) -> None:
    from app.data.store import store

    config, nodes = _create_quick_mesh_config(authenticated_client)

    response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/mesh/quick-generate",
        json={
            "mode": "free_mesh",
            "endpoint_ref_family": "ipv4",
            "gateway_node_ids": [nodes[0]["id"], nodes[1]["id"]],
            "leaf_assignments": {nodes[2]["id"]: nodes[1]["id"]},
            "use_preshared_key": True,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["generated_groups"] == 2
    links = store.list_peer_links(config["id"])
    assert len(links) == 4
    gateway_a_to_gateway_b = next(link for link in links if link.local_node_id == nodes[0]["id"] and link.peer_node_id == nodes[1]["id"])
    gateway_b_to_gateway_a = next(link for link in links if link.local_node_id == nodes[1]["id"] and link.peer_node_id == nodes[0]["id"])
    gateway_b_to_leaf = next(link for link in links if link.local_node_id == nodes[1]["id"] and link.peer_node_id == nodes[2]["id"])
    leaf_to_gateway_b = next(link for link in links if link.local_node_id == nodes[2]["id"] and link.peer_node_id == nodes[1]["id"])
    assert gateway_a_to_gateway_b.allowed_ips == f"{nodes[1]['virtual_ip']},{nodes[2]['virtual_ip']}"
    assert gateway_b_to_gateway_a.allowed_ips == nodes[0]["virtual_ip"]
    assert gateway_b_to_leaf.allowed_ips == nodes[2]["virtual_ip"]
    assert leaf_to_gateway_b.allowed_ips == config["virtual_subnet"]
    groups: dict[str, set[str | None]] = {}
    for link in links:
        groups.setdefault(link.link_group_id, set()).add(link.preshared_key)
    assert all(len(keys) == 1 and next(iter(keys)) for keys in groups.values())


def test_quick_generate_free_mesh_requires_all_nodes_assigned(authenticated_client: TestClient) -> None:
    config, nodes = _create_quick_mesh_config(authenticated_client)

    response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/mesh/quick-generate",
        json={
            "mode": "free_mesh",
            "endpoint_ref_family": "ipv4",
            "gateway_node_ids": [nodes[0]["id"]],
            "leaf_assignments": {nodes[1]["id"]: nodes[0]["id"]},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "QUICK_MESH_NODE_UNASSIGNED"
    assert body["error"]["detail"]["node_ids"] == [nodes[2]["id"]]


def test_port_forward_rule_generates_managed_hooks_on_to_endpoint(authenticated_client: TestClient) -> None:
    config, nodes = _create_quick_mesh_config(authenticated_client)

    response = authenticated_client.post(
        f"/api/v1/tools/port-forwards/configs/{config['id']}",
        json={
            "from_node_id": nodes[0]["id"],
            "from_port": 3000,
            "to_node_id": nodes[1]["id"],
            "to_port": 8443,
            "to_platform": "linux",
            "protocol": "tcp",
        },
    )

    assert response.status_code == 200
    rule = response.json()["data"]
    assert rule["from_node"]["name"] == nodes[0]["name"]
    assert rule["to_node"]["name"] == nodes[1]["name"]

    from_node = authenticated_client.get(f"/api/v1/nodes/{nodes[0]['id']}").json()["data"]
    to_node = authenticated_client.get(f"/api/v1/nodes/{nodes[1]['id']}").json()["data"]
    assert from_node["managed_hooks"]["post_up"] == []
    assert to_node["managed_hooks"]["post_up"][0]["source_id"] == rule["id"]
    assert "DNAT" in to_node["managed_hooks"]["post_up"][0]["command"]
    assert "sysctl" not in to_node["managed_hooks"]["post_up"][0]["command"]

    preview = authenticated_client.get(
        f"/api/v1/configs/{config['id']}/nodes/{nodes[1]['id']}/wg-preview"
    ).json()["data"]["content"]
    assert f"PostUp = {to_node['managed_hooks']['post_up'][0]['command']}" in preview
    assert f"PreDown = {to_node['managed_hooks']['pre_down'][0]['command']}" in preview


def test_port_forward_rule_rejects_duplicate_to_port(authenticated_client: TestClient) -> None:
    config, nodes = _create_quick_mesh_config(authenticated_client)
    payload = {
        "from_node_id": nodes[0]["id"],
        "from_port": 8080,
        "to_node_id": nodes[1]["id"],
        "to_port": 8081,
        "to_platform": "darwin",
        "protocol": "tcp",
    }

    assert authenticated_client.post(f"/api/v1/tools/port-forwards/configs/{config['id']}", json=payload).status_code == 200
    response = authenticated_client.post(
        f"/api/v1/tools/port-forwards/configs/{config['id']}",
        json={**payload, "from_node_id": nodes[2]["id"], "from_port": 8082},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PORT_FORWARD_TO_PORT_IN_USE"


def test_port_forward_rule_generates_all_protocol_hooks(authenticated_client: TestClient) -> None:
    config, nodes = _create_quick_mesh_config(authenticated_client)

    response = authenticated_client.post(
        f"/api/v1/tools/port-forwards/configs/{config['id']}",
        json={
            "from_node_id": nodes[0]["id"],
            "from_port": 5353,
            "to_node_id": nodes[1]["id"],
            "to_port": 15353,
            "to_platform": "darwin",
            "protocol": "all",
        },
    )

    assert response.status_code == 200
    rule = response.json()["data"]
    assert rule["protocol"] == "all"
    to_node = authenticated_client.get(f"/api/v1/nodes/{nodes[1]['id']}").json()["data"]
    assert "proto tcp" in to_node["managed_hooks"]["post_up"][0]["command"]
    assert "proto udp" in to_node["managed_hooks"]["post_up"][0]["command"]


def test_port_forward_rule_can_be_temporarily_disabled(authenticated_client: TestClient) -> None:
    config, nodes = _create_quick_mesh_config(authenticated_client)
    create_response = authenticated_client.post(
        f"/api/v1/tools/port-forwards/configs/{config['id']}",
        json={
            "from_node_id": nodes[0]["id"],
            "from_port": 9000,
            "to_node_id": nodes[1]["id"],
            "to_port": 19000,
            "to_platform": "linux",
            "protocol": "tcp",
        },
    )
    rule = create_response.json()["data"]

    response = authenticated_client.put(f"/api/v1/tools/port-forwards/{rule['id']}/enabled", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["data"]["enabled"] is False
    to_node = authenticated_client.get(f"/api/v1/nodes/{nodes[1]['id']}").json()["data"]
    assert to_node["managed_hooks"]["post_up"] == []
    listed = authenticated_client.get(f"/api/v1/tools/port-forwards/configs/{config['id']}").json()["data"]
    assert listed[0]["enabled"] is False


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
