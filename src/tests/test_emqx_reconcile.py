import httpx

from app.data.store import store


def test_emqx_reconcile_syncs_database_users_and_cleans_stale(authenticated_client, monkeypatch) -> None:
    from app.core.config import settings
    import app.services.emqx_reconcile_service as reconcile_module

    config_response = authenticated_client.post("/api/v1/configs", json={"name": "emqx_reconcile"})
    assert config_response.status_code == 200
    config = config_response.json()["data"]
    node_response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/nodes",
        json={
            "name": "edge-reconcile",
            "listen_port": 51831,
            "virtual_ip": "10.66.0.2/32",
            "node_type": "dynamic",
        },
    )
    assert node_response.status_code == 200
    node = node_response.json()["data"]
    store.mark_client_bound(
        config["id"],
        node["id"],
        username=node["id"],
        client_id=f"wfm-{node['id']}",
        password="db-secret",
    )

    calls: list[tuple[str, str]] = []

    class FakeEmqxService:
        def upsert_server_user(self) -> httpx.Response:
            calls.append(("upsert", "server"))
            return httpx.Response(204)

        def upsert_user(self, *, user_id: str, password: str) -> httpx.Response:
            calls.append(("upsert", f"{user_id}:{password}"))
            return httpx.Response(204)

        def list_user_ids(self) -> list[str]:
            return [node["id"], "node_stale", "admin"]

        def delete_user(self, *, user_id: str) -> httpx.Response:
            calls.append(("delete", user_id))
            return httpx.Response(204)

    monkeypatch.setattr(settings, "enable_mqtt_services", True)
    monkeypatch.setattr(reconcile_module, "emqx_service", FakeEmqxService())

    result = reconcile_module.emqx_reconcile_service.reconcile_all()

    assert result.server_users_synced == 1
    assert result.mqtt_credentials == 1
    assert result.node_users_synced == 1
    assert result.node_users_deleted == 1
    assert ("upsert", f"{node['id']}:db-secret") in calls
    assert ("delete", "node_stale") in calls
    assert ("delete", "admin") not in calls


def test_reset_client_state_is_database_first_when_emqx_fails(authenticated_client, monkeypatch) -> None:
    from app.core.config import settings
    import app.services.emqx_reconcile_service as reconcile_module

    config_response = authenticated_client.post("/api/v1/configs", json={"name": "emqx_reset_offline"})
    assert config_response.status_code == 200
    config = config_response.json()["data"]
    node_response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/nodes",
        json={
            "name": "edge-reset-offline",
            "listen_port": 51832,
            "virtual_ip": "10.66.0.3/32",
            "node_type": "dynamic",
        },
    )
    assert node_response.status_code == 200
    node = node_response.json()["data"]
    store.mark_client_bound(
        config["id"],
        node["id"],
        username=node["id"],
        client_id=f"wfm-{node['id']}",
        password="old-secret",
    )

    class FakeEmqxService:
        def delete_node_user(self, *, node_id: str) -> httpx.Response:
            raise OSError("emqx offline")

        def disconnect_node_client(self, *, node_id: str) -> httpx.Response:
            raise OSError("emqx offline")

    monkeypatch.setattr(settings, "enable_mqtt_services", True)
    monkeypatch.setattr(reconcile_module, "emqx_service", FakeEmqxService())

    response = authenticated_client.post(f"/api/v1/configs/{config['id']}/nodes/{node['id']}/reset-client")

    assert response.status_code == 200
    state = store.get_client_state(config["id"], node["id"])
    assert state["client_initialized"] is False
    assert state["mqtt_username"] == ""


def test_node_enable_transitions_preserve_credentials_and_coordinate_emqx(authenticated_client, monkeypatch) -> None:
    import app.services.control_plane_service as control_plane_module

    config_response = authenticated_client.post("/api/v1/configs", json={"name": "node_enable_reconcile"})
    assert config_response.status_code == 200
    config = config_response.json()["data"]
    node_response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/nodes",
        json={
            "name": "edge-enable",
            "listen_port": 51833,
            "virtual_ip": "10.66.0.4/32",
            "node_type": "dynamic",
        },
    )
    assert node_response.status_code == 200
    node = node_response.json()["data"]
    store.mark_client_bound(
        config["id"],
        node["id"],
        username=node["id"],
        client_id=f"wfm-{node['id']}",
        password="kept-secret",
    )
    calls: list[tuple[str, str]] = []

    class FakeReconcileService:
        def revoke_node_user(self, *, node_id: str) -> dict[str, bool]:
            calls.append(("revoke", node_id))
            return {"deleted": True, "disconnected": True}

        def reconcile_all(self) -> object:
            calls.append(("reconcile", "all"))
            return object()

    monkeypatch.setattr(control_plane_module, "emqx_reconcile_service", FakeReconcileService())

    disabled = control_plane_module.control_plane_service.update_node(node["id"], {"enabled": False})
    state_after_disable = store.get_client_state(config["id"], node["id"])
    enabled = control_plane_module.control_plane_service.update_node(node["id"], {"enabled": True})

    assert disabled["enabled"] is False
    assert enabled["enabled"] is True
    assert state_after_disable["client_initialized"] is True
    assert state_after_disable["mqtt_username"] == node["id"]
    assert calls == [("revoke", node["id"]), ("reconcile", "all")]


def test_delete_node_revokes_emqx_user(authenticated_client, monkeypatch) -> None:
    import app.services.control_plane_service as control_plane_module

    config_response = authenticated_client.post("/api/v1/configs", json={"name": "delete_node_reconcile"})
    assert config_response.status_code == 200
    config = config_response.json()["data"]
    node_response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/nodes",
        json={
            "name": "edge-delete",
            "listen_port": 51834,
            "virtual_ip": "10.66.0.5/32",
            "node_type": "dynamic",
        },
    )
    assert node_response.status_code == 200
    node = node_response.json()["data"]
    calls: list[tuple[str, str]] = []

    class FakeReconcileService:
        def revoke_node_user(self, *, node_id: str) -> dict[str, bool]:
            calls.append(("revoke", node_id))
            return {"deleted": True, "disconnected": True}

    monkeypatch.setattr(control_plane_module, "emqx_reconcile_service", FakeReconcileService())

    control_plane_module.control_plane_service.delete_node(node["id"])

    assert calls == [("revoke", node["id"])]


def test_config_enable_transitions_reconcile_emqx(authenticated_client, monkeypatch) -> None:
    import app.services.control_plane_service as control_plane_module

    config_response = authenticated_client.post("/api/v1/configs", json={"name": "config_reconcile"})
    assert config_response.status_code == 200
    config = config_response.json()["data"]
    calls: list[str] = []

    class FakeReconcileService:
        def reconcile_all(self) -> object:
            calls.append("reconcile")
            return object()

    monkeypatch.setattr(control_plane_module, "emqx_reconcile_service", FakeReconcileService())

    disabled = control_plane_module.control_plane_service.update_config(config["id"], {"enabled": False})
    enabled = control_plane_module.control_plane_service.update_config(config["id"], {"enabled": True})

    assert disabled["enabled"] is False
    assert enabled["enabled"] is True
    assert calls == ["reconcile", "reconcile"]
