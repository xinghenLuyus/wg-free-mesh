from __future__ import annotations

from app.mcp import catalog


def test_mcp_catalog_exposes_ai_guidance() -> None:
    overview = catalog.overview()
    tool_index = catalog.tool_index()
    workflows = catalog.workflows()
    schemas = catalog.schemas()

    assert overview["endpoint"] == "/mcp"
    assert "write" in overview["permissions"]
    assert "configs" in tool_index
    assert "write_quick_generate_mesh" in tool_index["mesh"]
    assert tool_index["snapshots"] == {
        "read_snapshots": "Read encrypted snapshot metadata.",
        "write_export_snapshot": "Create a 5-minute scoped download URL for one encrypted snapshot export.",
    }
    assert workflows["diagnose_offline_endpoint"]["steps"] == [
        "read_endpoint_status",
        "read_endpoint_logs",
        "read_node_sync_status",
        "read_wg_preview",
    ]
    assert workflows["backup_and_restore"]["steps"] == ["read_snapshots", "write_export_snapshot"]
    assert "quick_mesh_payload" in schemas
