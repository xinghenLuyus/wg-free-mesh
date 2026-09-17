# MCP Reference

The MCP endpoint is `/mcp`. Authenticate with:

```http
Authorization: Bearer <mcp-token>
```

MCP lets AI understand current system state and perform limited write operations after user confirmation.

## Resources

| Resource URI | Purpose |
| --- | --- |
| `wfm://help/overview` | MCP overview, authentication, permission boundary, and recommended first call. |
| `wfm://help/tool-index` | Tool list and tool purposes. |
| `wfm://help/workflows` | Common workflow examples. |
| `wfm://schema/payloads` | Write-tool payload semantics. |
| `wfm://system/status` | System status resource. |
| `wfm://configs` | Config list resource. |

## Read-only Tools

| Tool | Purpose |
| --- | --- |
| `read_system_status` | Read system status, endpoint counts, MQTT state, and issue summaries. |
| `read_configs` | List configs. |
| `read_config` | Read one config. |
| `read_config_overview` | Read a config overview projection. |
| `read_nodes` | List endpoints in a config. |
| `read_node_workspace` | Read an endpoint workspace. |
| `read_mesh_workspace` | Read the Mesh workspace from one endpoint's perspective. |
| `read_mesh_validation` | Validate a config Mesh topology. |
| `read_endpoint_status` | Read dynamic endpoint runtime status. |
| `read_endpoint_logs` | Read endpoint control logs. |
| `read_sync_status` | Read synchronization state for a config. |
| `read_node_sync_status` | Read synchronization state for one endpoint. |
| `read_wg_preview` | Read generated WireGuard or AmneziaWG config text. |
| `read_client_download_options` | Read client download options. |
| `read_config_bulk_options` | Read bulk config download options. |
| `read_port_forward_rules` | Read port-forward rules. |
| `read_snapshots` | Read snapshot metadata. |

## Write Tools

Write tools require a `write` token, and every execution requires MCP client confirmation.

| Tool | Purpose |
| --- | --- |
| `write_create_config` | Create a config. |
| `write_update_config` | Update a config. |
| `write_delete_config` | Delete a config. |
| `write_create_node` | Create an endpoint. |
| `write_update_node` | Update an endpoint. |
| `write_delete_node` | Delete an endpoint. |
| `write_create_tag` | Create a tag. |
| `write_apply_tag` | Apply a tag to endpoints. |
| `write_delete_tag` | Delete a tag. |
| `write_create_peer_link_group` | Create a bidirectional Mesh pair. |
| `write_update_peer_link_group` | Update a bidirectional Mesh pair. |
| `write_delete_peer_link_group` | Delete a bidirectional Mesh pair. |
| `write_quick_generate_mesh` | Delete and regenerate the config's Mesh pairs using Quick Mesh. |
| `write_sync_node` | Sync one endpoint. |
| `write_sync_all` | Sync all eligible endpoints. |
| `write_endpoint_control` | Send `start`, `stop`, `push_config`, or `wg_show`. |
| `write_probe_endpoints` | Probe dynamic endpoints. |
| `write_create_bind_command` | Create a client bind command. |
| `write_reset_client` | Reset client state and revoke MQTT credentials. |
| `write_create_port_forward_rule` | Create a port-forward rule. |
| `write_set_port_forward_rule_enabled` | Enable or disable a port-forward rule. |
| `write_delete_port_forward_rule` | Delete a port-forward rule. |
| `write_build_client_artifact` | Build a local client artifact or return the matching current-version GitHub Release URL. |
| `write_create_config_bulk_package` | Create a bulk config package and return a download URL. |
| `write_export_snapshot` | Export an existing snapshot and return a five-minute download URL. |

## Capabilities Not Exposed Through MCP

The following operations must be performed manually in the system UI:

- Create snapshots.
- Import snapshots.
- Restore snapshots.
- Delete snapshots.
- Enter or process snapshot passwords.

## Elicitation and Confirmation

Some write tools support MCP elicitation for missing parameters, such as a client download target, bulk-config endpoint selection, or snapshot ID.

Elicitation only completes parameters; it does not authorize execution. The write still enters the confirmation flow.

## Audit

MCP calls are recorded in the audit log. The AI Access page can filter by time, token name, and target endpoint, and can clear records by time range.
