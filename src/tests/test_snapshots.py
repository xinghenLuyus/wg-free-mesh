from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.data.store import store
from app.services.auth_service import auth_service

TEST_PASSWORD = "test-password-123"


def test_snapshot_restore_roundtrip_uses_application_database(authenticated_client: TestClient) -> None:
    created = authenticated_client.post("/api/v1/configs", json={"name": "snapshot_config"})
    assert created.status_code == 200
    config_id = created.json()["data"]["id"]

    snapshot_response = authenticated_client.post(
        "/api/v1/backups/snapshot",
        json={"note": "before delete", "password": TEST_PASSWORD},
    )
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()["data"]

    export_response = authenticated_client.get(f"/api/v1/backups/export/{snapshot['id']}")
    assert export_response.status_code == 200
    archive_path = snapshot["path"]
    with ZipFile(archive_path) as archive:
        assert "snapshot_payload.bin" in archive.namelist()
        assert "snapshot_manifest.json" in archive.namelist()
        assert "database.json" not in archive.namelist()
        assert "data/wg_free_mesh.db" not in archive.namelist()

    deleted = authenticated_client.delete(f"/api/v1/configs/{config_id}")
    assert deleted.status_code == 200
    missing = authenticated_client.get(f"/api/v1/configs/{config_id}")
    assert missing.status_code == 404

    restored = authenticated_client.post(f"/api/v1/backups/restore/{snapshot['id']}", json={"password": TEST_PASSWORD})
    assert restored.status_code == 200
    loaded = authenticated_client.get(f"/api/v1/configs/{config_id}")
    assert loaded.status_code == 200
    assert loaded.json()["data"]["name"] == "snapshot_config"


def test_snapshot_restore_preserves_client_mqtt_password(authenticated_client: TestClient) -> None:
    config_response = authenticated_client.post("/api/v1/configs", json={"name": "snapshot_mqtt"})
    assert config_response.status_code == 200
    config = config_response.json()["data"]
    node_response = authenticated_client.post(
        f"/api/v1/configs/{config['id']}/nodes",
        json={
            "name": "edge-a",
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
        password="snapshot-secret",
    )
    snapshot_response = authenticated_client.post(
        "/api/v1/backups/snapshot",
        json={"note": "mqtt credentials", "password": TEST_PASSWORD},
    )
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()["data"]

    with ZipFile(snapshot["path"]) as archive:
        assert "database.json" not in archive.namelist()

    store.mark_client_bound(
        config["id"],
        node["id"],
        username=node["id"],
        client_id=f"wfm-{node['id']}",
        password="changed-secret",
    )
    restored = authenticated_client.post(f"/api/v1/backups/restore/{snapshot['id']}", json={"password": TEST_PASSWORD})
    assert restored.status_code == 200
    recovery = restored.json()["data"]["recovery"]
    assert recovery["mqtt_credentials"] == 1

    credentials = store.list_restorable_mqtt_credentials()
    assert credentials == [
        {
            "config_id": config["id"],
            "node_id": node["id"],
            "username": node["id"],
            "client_id": f"wfm-{node['id']}",
            "password": "snapshot-secret",
        }
    ]


def test_snapshot_restore_includes_mcp_access_data(authenticated_client: TestClient) -> None:
    token = store.create_mcp_token(
        {
            "name": "Snapshot MCP",
            "permission": "write",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
    )
    audit = store.create_mcp_audit_log(
        {
            "token_id": token["id"],
            "token_name": token["name"],
            "permission": token["permission"],
            "target_kind": "tool",
            "target_name": "snapshot_test",
            "summary": "Snapshot includes MCP data",
            "result": "succeeded",
        }
    )
    snapshot_response = authenticated_client.post(
        "/api/v1/backups/snapshot",
        json={"note": "mcp data", "password": TEST_PASSWORD},
    )
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()["data"]

    store.revoke_mcp_token(token["id"])
    store.create_mcp_audit_log(
        {
            "token_id": token["id"],
            "token_name": token["name"],
            "permission": token["permission"],
            "target_kind": "tool",
            "target_name": "after_snapshot",
            "summary": "Should be replaced",
            "result": "succeeded",
        }
    )

    restored = authenticated_client.post(f"/api/v1/backups/restore/{snapshot['id']}", json={"password": TEST_PASSWORD})
    assert restored.status_code == 200

    tokens = store.list_mcp_tokens()
    assert [item["id"] for item in tokens] == [token["id"]]
    assert tokens[0]["token"] == token["token"]
    assert not tokens[0]["revoked_at"]
    audit_logs = store.list_mcp_audit_logs(limit=10)
    assert [item["id"] for item in audit_logs] == [audit["id"]]
    assert audit_logs[0]["target_name"] == "snapshot_test"


def test_snapshot_export_accepts_scoped_file_download_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    snapshot_response = client.post(
        "/api/v1/backups/snapshot",
        headers=auth_headers,
        json={"note": "download token", "password": TEST_PASSWORD},
    )
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()["data"]
    token = auth_service.create_file_download_token(kind="snapshot_export", resource_id=snapshot["id"])

    response = client.get(
        f"/api/v1/backups/export/{snapshot['id']}",
        params={"download_token": token["access_token"]},
    )

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")


def test_file_download_token_cannot_cross_resource(client: TestClient, auth_headers: dict[str, str]) -> None:
    snapshot_response = client.post(
        "/api/v1/backups/snapshot",
        headers=auth_headers,
        json={"note": "download token", "password": TEST_PASSWORD},
    )
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()["data"]
    token = auth_service.create_file_download_token(kind="snapshot_export", resource_id="other-snapshot")

    response = client.get(
        f"/api/v1/backups/export/{snapshot['id']}",
        params={"download_token": token["access_token"]},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DOWNLOAD_TOKEN_SCOPE_MISMATCH"
