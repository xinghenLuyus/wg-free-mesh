from __future__ import annotations


def overview() -> dict[str, object]:
    return {
        "name": "WG Free Mesh MCP",
        "purpose": (
            "Expose WG Free Mesh control-plane state and controlled write operations to AI agents. "
            "Use it to inspect Mesh configurations, nodes, WireGuard/AmneziaWG generated state, "
            "endpoint runtime status, managed port forwarding, downloads, and encrypted snapshots."
        ),
        "endpoint": "/mcp",
        "authentication": {
            "type": "Bearer token",
            "header": "Authorization: Bearer <mcp-token>",
            "token_management": "/api/v1/mcp-access/tokens",
        },
        "permissions": {
            "read": "Can call resources and read_* tools only.",
            "write": "Can call read tools and write_* tools. Every write still requires MCP client elicitation confirmation.",
        },
        "write_safety": [
            "All write_* tools require a write token.",
            "All write_* tools ask the MCP client to confirm the operation and impact before executing.",
            "If the client does not support elicitation or the user rejects the prompt, the write is not executed.",
            "Successful and failed MCP calls are written to the MCP audit log.",
        ],
        "recommended_first_calls": [
            "read_system_status",
            "read_configs",
            "read_config_overview when a specific config_id is known",
        ],
    }


def tool_index() -> dict[str, object]:
    return {
        "system": {
            "read_system_status": "Read global service state, topology summary, sync issue summary, and MQTT status.",
        },
        "configs": {
            "read_configs": "List Mesh configurations.",
            "read_config": "Read one configuration object by config_id.",
            "read_config_overview": "Read the main control-page projection for one configuration.",
            "write_create_config": "Create a Mesh configuration.",
            "write_update_config": "Update a Mesh configuration and refresh derived state.",
            "write_delete_config": "Delete a Mesh configuration and related managed state.",
        },
        "nodes": {
            "read_nodes": "List nodes in a configuration.",
            "read_node_workspace": "Read a node detail workspace, including endpoint status when applicable.",
            "write_create_node": "Create a dynamic or static endpoint.",
            "write_update_node": "Update endpoint identity, addresses, tags, hooks, AWG local parameters, or enabled state.",
            "write_delete_node": "Delete one endpoint and related managed relationships.",
            "write_create_tag": "Create a tag in a configuration.",
            "write_apply_tag": "Apply a tag to selected nodes.",
            "write_delete_tag": "Delete a tag from a configuration and its nodes.",
        },
        "mesh": {
            "read_mesh_workspace": "Read Mesh links and validation from one node's perspective.",
            "read_mesh_validation": "Validate the whole Mesh topology for one configuration.",
            "read_wg_preview": "Read generated WireGuard or AmneziaWG config text for one node.",
            "write_create_peer_link_group": "Create a bidirectional Mesh peer-link group.",
            "write_update_peer_link_group": "Update a bidirectional Mesh peer-link group.",
            "write_delete_peer_link_group": "Delete a bidirectional Mesh peer-link group.",
            "write_quick_generate_mesh": "Delete and regenerate Mesh links using hub_spoke, full_mesh, or free_mesh.",
        },
        "sync_and_runtime": {
            "read_sync_status": "Read sync state for all nodes in one configuration.",
            "read_node_sync_status": "Read sync state for one node.",
            "read_endpoint_status": "Read endpoint runtime/client/config status.",
            "read_endpoint_logs": "Read endpoint control logs.",
            "write_sync_node": "Sync one node and push staged config when eligible.",
            "write_sync_all": "Sync all eligible nodes in one configuration.",
            "write_endpoint_control": "Send start, stop, push_config, or wg_show to one endpoint.",
            "write_probe_endpoints": "Ask dynamic endpoints to report status over MQTT.",
            "write_create_bind_command": "Create a one-time client bind command.",
            "write_reset_client": "Reset client state and revoke MQTT access for one dynamic endpoint.",
        },
        "tools": {
            "read_client_download_options": "Read supported client download/build options.",
            "write_build_client_artifact": (
                "Build a local client artifact or return a GitHub Release download URL "
                "matching the current server version."
            ),
            "write_create_config_bulk_package": "Create a bulk config download package.",
        },
        "port_forward": {
            "read_port_forward_rules": "Read WFM-managed port-forward rules for one configuration.",
            "write_create_port_forward_rule": "Create a managed port-forward rule.",
            "write_set_port_forward_rule_enabled": "Enable or disable a managed port-forward rule.",
            "write_delete_port_forward_rule": "Delete a managed port-forward rule.",
        },
        "snapshots": {
            "read_snapshots": "Read encrypted snapshot metadata.",
            "write_export_snapshot": "Create a 5-minute scoped download URL for one encrypted snapshot export.",
        },
    }


def workflows() -> dict[str, object]:
    return {
        "inspect_system": {
            "goal": "Understand whether the deployment is healthy.",
            "steps": ["read_system_status", "read_configs"],
        },
        "inspect_config_before_change": {
            "goal": "Gather enough context before editing one Mesh configuration.",
            "steps": ["read_config_overview", "read_mesh_validation", "read_sync_status"],
        },
        "diagnose_offline_endpoint": {
            "goal": "Find why one dynamic endpoint looks offline or stale.",
            "steps": ["read_endpoint_status", "read_endpoint_logs", "read_node_sync_status", "read_wg_preview"],
        },
        "create_basic_mesh": {
            "goal": "Create a config, add nodes, generate links, then sync.",
            "steps": ["write_create_config", "write_create_node", "write_quick_generate_mesh", "write_sync_all"],
            "notes": "Prefer read_config_overview before write_quick_generate_mesh so gateway/public-address requirements are clear.",
        },
        "regenerate_quick_mesh": {
            "goal": "Replace all Mesh pairs in one configuration using quick networking.",
            "steps": ["read_config_overview", "read_mesh_validation", "write_quick_generate_mesh", "read_mesh_validation"],
            "warning": "write_quick_generate_mesh deletes existing Mesh pairs in the configuration before creating new ones.",
        },
        "create_port_forward": {
            "goal": "Expose one virtual source port to a destination node service port.",
            "steps": ["read_nodes", "read_port_forward_rules", "write_create_port_forward_rule", "read_port_forward_rules"],
            "notes": "The destination platform must be linux or darwin because WFM implements this with managed lifecycle hooks.",
        },
        "backup_and_restore": {
            "goal": "Inspect and export encrypted application snapshots.",
            "steps": ["read_snapshots", "write_export_snapshot"],
            "warning": "Snapshot create, import, restore, and delete are intentionally not available through MCP. Use the system UI.",
        },
    }


def schemas() -> dict[str, object]:
    return {
        "config_payload": {
            "used_by": ["write_create_config", "write_update_config"],
            "notes": [
                "tunnel_protocol is wireguard or amneziawg_2.",
                "When switching to wireguard, AWG-specific fields are cleared by backend rules.",
                "When switching to amneziawg_2, leave AWG fields empty to let the backend generate safe defaults.",
            ],
        },
        "node_payload": {
            "used_by": ["write_create_node", "write_update_node"],
            "notes": [
                "node_type is dynamic for client-managed endpoints or static for manually managed endpoints.",
                "Dynamic endpoints can bind to MQTT only when MQTT services are enabled.",
                "pre_up/post_up/pre_down/post_down are wg-quick or awg-quick lifecycle hooks.",
                "AWG local fields only affect AmneziaWG configurations.",
            ],
        },
        "peer_link_group_payload": {
            "used_by": ["write_create_peer_link_group", "write_update_peer_link_group"],
            "notes": [
                "A group is bidirectional: forward and reverse describe each direction independently.",
                "Use endpoint_mode=auto for normal public-address based links.",
                "Use endpoint_mode=none for routes that should not write Endpoint.",
            ],
        },
        "quick_mesh_payload": {
            "used_by": ["write_quick_generate_mesh"],
            "notes": [
                "hub_spoke uses one gateway node and branches route the config subnet through it.",
                "full_mesh connects all eligible nodes directly.",
                "free_mesh uses multiple gateway nodes plus leaf-to-gateway assignments.",
            ],
        },
        "port_forward_payload": {
            "used_by": ["write_create_port_forward_rule"],
            "notes": [
                "from_node_id/from_port identify the service side.",
                "to_node_id/to_port identify the exposed forwarding entrypoint and lifecycle hook owner.",
                "protocol can be tcp, udp, or all.",
            ],
        },
    }
