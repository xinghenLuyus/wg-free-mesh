import json
from zipfile import ZipFile

from fastapi.testclient import TestClient


def test_snapshot_restore_roundtrip_uses_application_database(authenticated_client: TestClient) -> None:
    created = authenticated_client.post("/api/v1/configs", json={"name": "snapshot_config"})
    assert created.status_code == 200
    config_id = created.json()["data"]["id"]

    snapshot_response = authenticated_client.post("/api/v1/backups/snapshot", content="before delete")
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()["data"]

    export_response = authenticated_client.get(f"/api/v1/backups/export/{snapshot['id']}")
    assert export_response.status_code == 200
    archive_path = snapshot["path"]
    with ZipFile(archive_path) as archive:
        assert "database.json" in archive.namelist()
        assert "data/wg_free_mesh.db" not in archive.namelist()

    deleted = authenticated_client.delete(f"/api/v1/configs/{config_id}")
    assert deleted.status_code == 200
    missing = authenticated_client.get(f"/api/v1/configs/{config_id}")
    assert missing.status_code == 404

    restored = authenticated_client.post(f"/api/v1/backups/restore/{snapshot['id']}")
    assert restored.status_code == 200
    loaded = authenticated_client.get(f"/api/v1/configs/{config_id}")
    assert loaded.status_code == 200
    assert loaded.json()["data"]["name"] == "snapshot_config"


def test_snapshot_restore_preserves_client_mqtt_password(authenticated_client: TestClient) -> None:
    from app.data.store import store

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
    snapshot_response = authenticated_client.post("/api/v1/backups/snapshot", content="mqtt credentials")
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()["data"]

    with ZipFile(snapshot["path"]) as archive:
        database_payload = json.loads(archive.read("database.json").decode("utf-8"))
    client_rows = database_payload["tables"]["node_client_state"]
    assert any(row["node_id"] == node["id"] and row["mqtt_password"] == "snapshot-secret" for row in client_rows)

    store.mark_client_bound(
        config["id"],
        node["id"],
        username=node["id"],
        client_id=f"wfm-{node['id']}",
        password="changed-secret",
    )
    restored = authenticated_client.post(f"/api/v1/backups/restore/{snapshot['id']}")
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
