import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect

from app.domain.models import now_utc
from app.services.runtime_observation_service import (
    RuntimeObservationService,
    endpoint_state,
    mesh_health,
)


def sample(handshake="1", stopped=False):
    return {
        "interface_state": "stopped" if stopped else "running",
        "peer": {"latest_handshake": handshake},
    }


@pytest.mark.parametrize(
    "online,running,fresh,expected",
    [
        (False, True, True, "offline"),
        (True, False, True, "not_started"),
        (True, True, True, "online"),
        (True, True, False, "not_started"),
    ],
)
def test_endpoint_states(online, running, fresh, expected):
    runtime = SimpleNamespace(
        online=online,
        wg_running=running,
        wg_runtime_state="running" if running else "stopped",
        wg_observed_at=now_utc() - timedelta(seconds=0 if fresh else 151),
    )
    assert endpoint_state(runtime) == expected


@pytest.mark.parametrize(
    "sa,sb,oa,ob,a,b,result",
    [
        (True, True, False, False, None, None, None),
        (False, True, True, False, sample(), None, "healthy"),
        (False, True, True, False, sample("0"), None, "interrupted"),
        (False, False, True, True, sample(), sample(), "healthy"),
        (False, False, True, True, sample(), sample("0"), "interrupted"),
        (False, False, True, False, sample(), None, "healthy"),
        (False, False, False, False, None, None, "interrupted"),
        (False, False, True, True, sample(), sample(stopped=True), "interrupted"),
        (False, True, True, False, None, None, "interrupted"),
    ],
)
def test_mesh_matrix(sa, sb, oa, ob, a, b, result):
    assert mesh_health(sa, sb, oa, ob, a, b)["state"] == result


@pytest.mark.parametrize(
    "types,expected",
    [
        (("dynamic", "dynamic"), "interrupted"),
        (("dynamic", "static"), "interrupted"),
        (("static", "static"), None),
    ],
)
def test_mesh_health_survives_http_serialization(
    authenticated_client, mqtt_feature, monkeypatch, types, expected
):
    client = authenticated_client
    config = client.post("/api/v1/configs", json={"name": "mesh-http-health"}).json()["data"]
    config_id = config["id"]
    nodes = []
    for index, node_type in enumerate(types):
        response = client.post(
            f"/api/v1/configs/{config_id}/nodes",
            json={
                "name": f"node-{index}",
                "node_type": node_type,
                "virtual_ip": f"10.66.0.{index + 1}/32",
            },
        )
        assert response.status_code == 200
        nodes.append(response.json()["data"])
    response = client.post(
        f"/api/v1/configs/{config_id}/peer-links",
        json={
            "forward": {
                "local_node_id": nodes[0]["id"],
                "peer_node_id": nodes[1]["id"],
                "allowed_ips": nodes[1]["virtual_ip"],
                "endpoint_mode": "none",
            },
            "reverse": {
                "local_node_id": nodes[1]["id"],
                "peer_node_id": nodes[0]["id"],
                "allowed_ips": nodes[0]["virtual_ip"],
                "endpoint_mode": "none",
            },
        },
    )
    assert response.status_code == 200
    from app.services.control_plane_service import control_plane_service
    from app.api.v1.routers.mesh import MeshWorkspaceResponse

    for node in nodes:
        url = f"/api/v1/configs/{config_id}/nodes/{node['id']}/mesh-workspace"
        response = client.get(url)
        assert response.status_code == 200
        workspace = response.json()["data"]
        health = workspace["connections"][0]["health"]
        assert health["state"] == expected
        assert health["reason"] == (
            "both_offline"
            if types == ("dynamic", "dynamic")
            else "static"
            if expected is None
            else "no_observation"
        )
        assert health["observations"] == []
        assert workspace["readonly"] is False
        assert workspace["connections"][0]["readonly"] is False
        assert workspace["connections"][0]["peer_disabled"] is False
        # SSE publishes this service projection; it must use the same health contract.
        projection = control_plane_service.mesh_workspace(config_id, node["id"])
        assert projection["connections"][0]["health"] == health
        assert (
            MeshWorkspaceResponse.model_validate(projection).model_dump(mode="json")["connections"][
                0
            ]["health"]
            == health
        )

    if types == ("dynamic", "dynamic"):
        from app.services.runtime_observation_service import runtime_observation_service

        healthy = {
            "state": "healthy",
            "reason": "handshake",
            "observations": [
                {
                    "node_id": nodes[0]["id"],
                    "observed_at": now_utc().isoformat(),
                    "interface_state": "running",
                    "peer": {
                        "latest_handshake": "1720000000",
                        "rx_bytes": "9007199254740993",
                        "tx_bytes": "18446744073709551615",
                    },
                }
            ],
        }
        monkeypatch.setattr(runtime_observation_service, "health", lambda *args: healthy)
        url = f"/api/v1/configs/{config_id}/nodes/{nodes[0]['id']}/mesh-workspace"
        assert client.get(url).json()["data"]["connections"][0]["health"] == healthy
        assert (
            control_plane_service.mesh_workspace(config_id, nodes[0]["id"])["connections"][0][
                "health"
            ]
            == healthy
        )


def test_structured_validation_preserves_precision_and_excludes_secrets():
    payload = {
        "interface_state": "running",
        "interface_public_key": "local",
        "tunnel_protocol": "wireguard",
        "config_sha256": "hash",
        "interface_name": "wg0",
        "private_key": "secret",
        "peers": [
            {
                "public_key": "peer",
                "latest_handshake": "0",
                "rx_bytes": "18446744073709551615",
                "tx_bytes": "0",
                "preshared_key": "secret",
            }
        ],
    }
    result = RuntimeObservationService.validate(
        payload, {"public_key": "local", "protocol": "wireguard"}
    )
    assert result["peers"][0]["rx_bytes"] == "18446744073709551615"
    assert "secret" not in str(result)
    payload["peers"][0]["rx_bytes"] = "-1"
    with pytest.raises(ValueError):
        RuntimeObservationService.validate(
            payload, {"public_key": "local", "protocol": "wireguard"}
        )


def test_late_automatic_response_never_enters_manual_log():
    service = RuntimeObservationService()
    assert asyncio.run(
        service.receive(
            "cfg",
            "node",
            "info/ack",
            {"request_id": "obs-expired", "payload": {"action": "runtime_snapshot"}},
        )
    )
    assert asyncio.run(
        service.receive("cfg", "node", "detect/ack", {"request_id": "obs-expired", "payload": {}})
    )
    assert not asyncio.run(
        service.receive(
            "cfg", "node", "info/ack", {"request_id": "manual", "payload": {"action": "wg_show"}}
        )
    )


def test_watch_authentication_and_validation(client, authenticated_client):
    assert client.post(
        "/api/v1/configs/unknown/runtime-watch", json={"viewer_id": "test"}
    ).status_code in (401, 404)
    cfg = authenticated_client.post("/api/v1/configs", json={"name": "watch-test"}).json()["data"]
    url = f"/api/v1/configs/{cfg['id']}/runtime-watch"
    assert authenticated_client.post(url, json={"viewer_id": "view-1"}).status_code == 200
    assert (
        authenticated_client.post(url, json={"viewer_id": "; arbitrary command"}).status_code == 422
    )
    assert (
        authenticated_client.post(url, json={"viewer_id": "view-1", "active": False}).status_code
        == 200
    )
    from app.data.connection import get_engine

    assert "node_runtime_observations" in inspect(get_engine()).get_table_names()


def test_reset_invalidates_restored_observations():
    service = RuntimeObservationService()
    previous = service.collector_id
    service.reset()
    assert previous != service.collector_id
    assert not service.leases and not service.pending


def test_manual_scope_rejects_command_injection_and_non_boolean(authenticated_client):
    endpoint = "/api/v1/configs/cfg/nodes/node/endpoint/control"
    for payload in [
        {"action": "wg_show; id"},
        {"action": "wg_show", "current_interface_only": "true"},
        {"action": "wg_show", "current_interface_only": ["wg0", ";id"]},
    ]:
        assert authenticated_client.post(endpoint, json=payload).status_code == 422


def test_collection_roundtrip_is_bounded_and_does_not_create_logs(
    authenticated_client, monkeypatch
):
    import json
    from app.core.config import settings
    from app.data.connection import connect
    from app.data.store import store
    from app.services.mqtt_ingress_service import mqtt_ingress_service
    from app.services.node_runtime_service import node_runtime_service

    cfg = authenticated_client.post(
        "/api/v1/configs", json={"name": "observation-roundtrip"}
    ).json()["data"]
    node = authenticated_client.post(
        f"/api/v1/configs/{cfg['id']}/nodes", json={"name": "local", "node_type": "static"}
    ).json()["data"]
    monkeypatch.setattr(settings, "enable_mqtt_services", True)
    with connect() as db:
        db.execute("UPDATE nodes SET node_type='dynamic' WHERE id=?", (node["id"],))
        db.execute(
            "UPDATE node_client_state SET client_initialized=1 WHERE node_id=?", (node["id"],)
        )
    service = RuntimeObservationService()
    sent = []

    async def no_publish(*args):
        pass

    async def publish(**kwargs):
        request = kwargs["payload"]
        sent.append(kwargs["kind"])
        payload = {"status": "applied", "wg_online": True, "capabilities": ["runtime_snapshot_v1"]}
        if kwargs["kind"] == "info":
            payload = {
                "status": "applied",
                "interface_state": "running",
                "interface_public_key": node["public_key"],
                "interface_name": "wg0",
                "tunnel_protocol": "wireguard",
                "config_sha256": "hash",
                "peers": [
                    {
                        "public_key": "remote",
                        "latest_handshake": "123",
                        "rx_bytes": "9007199254740993",
                        "tx_bytes": "0",
                    }
                ],
            }
        await service.receive(
            cfg["id"],
            node["id"],
            kwargs["kind"] + "/ack",
            {**request, "session_id": "session-1", "payload": payload},
        )

    monkeypatch.setattr(mqtt_ingress_service, "publish_to_node", publish)
    monkeypatch.setattr(node_runtime_service, "_publish_runtime_scope", no_publish)
    asyncio.run(service.collect(cfg["id"], node["id"], True))
    asyncio.run(service.collect(cfg["id"], node["id"], True))
    assert sent == ["detect", "info"]
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM node_runtime_observations WHERE node_id=?", (node["id"],)
        ).fetchall()
        assert len(rows) == 1 and rows[0]["query_status"] == "ok"
        assert json.loads(rows[0]["snapshot_json"])["peers"][0]["rx_bytes"] == "9007199254740993"
        assert not db.execute(
            "SELECT * FROM endpoint_control_logs WHERE node_id=?", (node["id"],)
        ).fetchall()
    assert service.observation(cfg["id"], node["id"], "remote")["peer"]["latest_handshake"] == "123"
    # Duplicate and late responses cannot overwrite the completed snapshot.
    assert asyncio.run(
        service.receive(
            cfg["id"],
            node["id"],
            "info/ack",
            {"request_id": rows[0]["request_id"], "payload": {"status": "failed"}},
        )
    )
    assert store.get_runtime(cfg["id"], node["id"]).wg_running


def test_visible_leases_expire_and_static_nodes_are_not_polled(authenticated_client, monkeypatch):
    from app.core.config import settings
    from app.data.connection import connect
    from app.data.store import store

    cfg = authenticated_client.post("/api/v1/configs", json={"name": "lease-test"}).json()["data"]
    node = authenticated_client.post(
        f"/api/v1/configs/{cfg['id']}/nodes", json={"name": "static", "node_type": "static"}
    ).json()["data"]
    service = RuntimeObservationService()
    service.watch("visible", cfg["id"], node["id"], True)
    assert service.targets() == {}
    monkeypatch.setattr(settings, "enable_mqtt_services", True)
    store.get_client_state(cfg["id"], node["id"])
    with connect() as db:
        db.execute("UPDATE nodes SET node_type='dynamic' WHERE id=?", (node["id"],))
        db.execute(
            "UPDATE node_client_state SET client_initialized=1 WHERE node_id=?", (node["id"],)
        )
    assert service.targets() == {(cfg["id"], node["id"]): True}
    service.leases["visible"] = (0, cfg["id"], node["id"], "mesh")
    assert service.targets() == {} and not service.leases
