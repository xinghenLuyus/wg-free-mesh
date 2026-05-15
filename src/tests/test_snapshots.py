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

