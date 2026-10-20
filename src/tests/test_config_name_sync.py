from uuid import uuid4

from fastapi.testclient import TestClient


def test_rename_changes_configuration_hash(authenticated_client: TestClient) -> None:
    client = authenticated_client
    name = f"names_{uuid4().hex[:8]}"
    config = client.post("/api/v1/configs", json={"name": name}).json()["data"]
    node = client.post(
        f"/api/v1/configs/{config['id']}/nodes", json={"name": "a", "node_type": "static"}
    ).json()["data"]
    url = f"/api/v1/configs/{config['id']}/nodes/{node['id']}/wg-preview"
    original = client.get(url).json()["data"]
    assert client.put(f"/api/v1/configs/{config['id']}", json={"name": f"{name}_new"}).status_code == 200
    renamed_config = client.get(url).json()["data"]
    assert renamed_config["sha256"] != original["sha256"]
    assert f"# Interface: {name}_new-a" in renamed_config["content"]
    assert client.put(f"/api/v1/nodes/{node['id']}", json={"name": "b"}).status_code == 200
    renamed_node = client.get(url).json()["data"]
    assert renamed_node["sha256"] != renamed_config["sha256"]
    assert f"# Interface: {name}_new-b" in renamed_node["content"]
