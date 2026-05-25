from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
import pytest

from app.services.control_plane_service import control_plane_service


def test_mcp_endpoint_requires_bearer_token(client: TestClient) -> None:
    pytest.importorskip("mcp")

    response = client.post("/mcp")
    slash_response = client.post("/mcp/")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert slash_response.status_code == 401
    assert slash_response.headers["www-authenticate"] == "Bearer"


def test_mcp_token_lifecycle_and_audit(authenticated_client: TestClient) -> None:
    created = authenticated_client.post(
        "/api/v1/mcp-access/tokens",
        json={
            "name": "Claude Code",
            "permission": "write",
            "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        },
    )

    assert created.status_code == 200
    token = created.json()["data"]
    assert token["token"].startswith("wfm_mcp_")
    assert control_plane_service.find_active_mcp_token(token["token"])["id"] == token["id"]

    control_plane_service.create_mcp_audit_log(
        {
            "token_id": token["id"],
            "token_name": token["name"],
            "permission": token["permission"],
            "target_kind": "tool",
            "target_name": "read_configs",
            "summary": "Read config list",
            "result": "succeeded",
        }
    )
    audit = authenticated_client.get("/api/v1/mcp-access/audit")

    assert audit.status_code == 200
    assert audit.json()["data"][0]["target_name"] == "read_configs"

    filtered = authenticated_client.get(
        "/api/v1/mcp-access/audit",
        params={
            "created_from": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
            "created_to": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "token_name": "claude",
            "target_name": "read_configs",
        },
    )

    assert filtered.status_code == 200
    assert len(filtered.json()["data"]) == 1

    unmatched = authenticated_client.get("/api/v1/mcp-access/audit", params={"target_name": "write_config"})

    assert unmatched.status_code == 200
    assert unmatched.json()["data"] == []

    revoked = authenticated_client.post(f"/api/v1/mcp-access/tokens/{token['id']}/revoke")

    assert revoked.status_code == 200
    assert revoked.json()["data"]["revoked_at"]
    assert control_plane_service.find_active_mcp_token(token["token"]) is None

    cleanup = authenticated_client.request(
        "DELETE",
        "/api/v1/mcp-access/audit",
        json={
            "created_from": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
            "created_to": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        },
    )

    assert cleanup.status_code == 200
    assert cleanup.json()["data"]["deleted_count"] == 1
    assert authenticated_client.get("/api/v1/mcp-access/audit").json()["data"] == []
