import json

import pytest

from app.data.store import store
from app.domain.models import now_utc
from app.services.runtime_observation_service import runtime_observation_service


def create_board(client, types=("dynamic", "dynamic", "static")):
    response = client.post("/api/v1/configs", json={"name": "topology-test"})
    assert response.status_code == 200
    config = response.json()["data"]
    nodes = []
    for index, kind in enumerate(types):
        response = client.post(
            f"/api/v1/configs/{config['id']}/nodes",
            json={
                "name": f"node-{index}",
                "node_type": kind,
                "virtual_ip": f"10.66.0.{index + 1}/32",
            },
        )
        assert response.status_code == 200
        nodes.append(response.json()["data"])
    response = client.post(
        f"/api/v1/configs/{config['id']}/peer-links",
        json={
            "forward": {
                "local_node_id": nodes[0]["id"],
                "peer_node_id": nodes[1]["id"],
                "allowed_ips": "0.0.0.0/0",
                "persistent_keepalive": 25,
                "endpoint_mode": "manual",
                "endpoint_manual_host": "192.0.2.2",
                "endpoint_manual_port": 51820,
            },
            "reverse": {
                "local_node_id": nodes[1]["id"],
                "peer_node_id": nodes[0]["id"],
                "allowed_ips": nodes[0]["virtual_ip"],
                "persistent_keepalive": 0,
                "endpoint_mode": "manual",
                "endpoint_manual_host": "192.0.2.1",
                "endpoint_manual_port": 51820,
            },
        },
    )
    assert response.status_code == 200
    return config, nodes


def test_topology_http_is_secret_free_and_keeps_direction(authenticated_client, mqtt_feature):
    config, nodes = create_board(authenticated_client)
    response = authenticated_client.get(f"/api/v1/configs/{config['id']}/topology")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["nodes"]) == 3  # Isolated nodes remain in the graph.
    assert len(data["connections"]) == 1
    edge = data["connections"][0]
    assert edge["source"] < edge["target"]
    directions = {d["local_node_id"]: d for d in (edge["forward"], edge["reverse"])}
    assert directions[nodes[0]["id"]]["allowed_ips"] == "0.0.0.0/0"
    assert directions[nodes[0]["id"]]["persistent_keepalive"] == 25
    assert directions[nodes[1]["id"]]["persistent_keepalive"] == 0
    assert edge["health"]["state"] == "interrupted"
    assert edge["health"]["reason"] == "both_offline"
    assert edge["validation_errors"] == []  # Offline is not a topology validation failure.
    assert not data["issues"]
    body = json.dumps(data)
    assert all(n["private_key"] not in body for n in nodes)
    assert "private_key" not in body and '"preshared_key"' not in body
    # All nodes are scoped to this config, including isolated nodes.
    assert {n["id"] for n in data["nodes"]} == {n["id"] for n in nodes}


def test_board_retains_both_observation_sources(authenticated_client, mqtt_feature, monkeypatch):
    from app.services.control_plane_service import control_plane_service

    async def no_push(*args, **kwargs):
        pass

    monkeypatch.setattr(control_plane_service, "publish_pending_config_pushes", no_push)
    config, nodes = create_board(authenticated_client)
    for index in (0, 1):
        node, peer = nodes[index], nodes[1 - index]
        store.mark_client_bound(
            config["id"], node["id"], username=node["id"], client_id=node["id"], password="test"
        )
        store.record_detect_ack(
            config["id"], node["id"], session_id="board-session", wg_online=True
        )
        request = f"obs-board-{index}"
        observed = now_utc().isoformat()
        store.start_observation(config["id"], node["id"], request, observed)
        store.complete_observation(
            node["id"],
            request,
            observed,
            "board-session",
            runtime_observation_service.collector_id,
            {
                "interface_state": "running",
                "interface_public_key": node["public_key"],
                "tunnel_protocol": "wireguard",
                "interface_name": "wg0",
                "config_sha256": "hash",
                "peers": [
                    {
                        "public_key": peer["public_key"],
                        "latest_handshake": "1720000000",
                        "rx_bytes": "9007199254740993",
                        "tx_bytes": "18446744073709551615",
                    }
                ],
            },
        )
    for index in (0, 1):
        assert (
            runtime_observation_service.observation(
                config["id"], nodes[index]["id"], nodes[1 - index]["public_key"]
            )
            is not None
        )
        assert store.get_runtime(config["id"], nodes[index]["id"]).online
    response = authenticated_client.get(f"/api/v1/configs/{config['id']}/topology")
    assert response.status_code == 200
    health = response.json()["data"]["connections"][0]["health"]
    assert health["state"] == "healthy"
    assert {sample["node_id"] for sample in health["observations"]} == {n["id"] for n in nodes[:2]}
    assert all(
        sample["peer"]["rx_bytes"] == "9007199254740993" for sample in health["observations"]
    )


@pytest.mark.parametrize("mqtt_enabled", [True, False])
def test_static_board_still_draws_without_health(
    authenticated_client, mqtt_feature, monkeypatch, mqtt_enabled
):
    from app.core.config import settings

    config, nodes = create_board(authenticated_client, ("static", "static"))
    monkeypatch.setattr(settings, "enable_mqtt_services", mqtt_enabled)
    response = authenticated_client.get(f"/api/v1/configs/{config['id']}/topology")
    assert response.status_code == 200
    data = response.json()["data"]
    assert all(n["endpoint_state"] is None for n in data["nodes"])
    assert data["connections"][0]["health"]["state"] is None


def test_topology_requires_session_and_valid_config(client, authenticated_client):
    # Authenticated requests must not silently produce an empty board for a bad ID.
    assert authenticated_client.get("/api/v1/configs/missing/topology").status_code == 404
    token = client.headers.pop("Authorization")
    try:
        assert client.get("/api/v1/configs/missing/topology").status_code == 401
    finally:
        client.headers["Authorization"] = token


@pytest.mark.parametrize("duplicate_enabled", [True, False])
def test_board_distinguishes_duplicate_validation_from_disabled_pairs(
    authenticated_client, monkeypatch, duplicate_enabled
):
    config, _ = create_board(authenticated_client, ("static", "static"))
    links = store.list_peer_links(config["id"])
    duplicates = [
        link.model_copy(
            update={
                "id": f"duplicate-{index}",
                "link_group_id": "duplicate-group",
                "enabled": duplicate_enabled,
            }
        )
        for index, link in enumerate(links)
    ]
    monkeypatch.setattr(store, "list_peer_links", lambda config_id: links + duplicates)
    response = authenticated_client.get(f"/api/v1/configs/{config['id']}/topology")
    assert response.status_code == 200
    edges = response.json()["data"]["connections"]
    assert len(edges) == 2
    for edge in edges:
        assert edge["health"]["state"] is None  # Static links still carry validation errors.
        assert bool(edge["validation_errors"]) is duplicate_enabled
        if duplicate_enabled:
            assert "Duplicate enabled peer links" in edge["validation_errors"][0]


@pytest.mark.parametrize("failure", ["endpoint", "directions"])
def test_board_reports_group_validation_errors(
    authenticated_client, mqtt_feature, monkeypatch, failure
):
    from app.domain.models import EndpointMode

    config, _ = create_board(authenticated_client)
    links = store.list_peer_links(config["id"])
    if failure == "directions":
        links = links[:1]
    else:
        links = [link.model_copy(update={"endpoint_mode": EndpointMode.auto}) for link in links]
    monkeypatch.setattr(store, "list_peer_links", lambda config_id: links)
    response = authenticated_client.get(f"/api/v1/configs/{config['id']}/topology")
    assert response.status_code == 200
    edge = response.json()["data"]["connections"][0]
    assert edge["validation_errors"]
    expected = (
        "incomplete or conflicting directions"
        if failure == "directions"
        else "both sides have no public endpoint"
    )
    assert any(expected in message for message in edge["validation_errors"])
