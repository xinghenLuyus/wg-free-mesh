from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from starlette.types import ASGIApp

from app.mcp import operations
from app.mcp.access import McpBearerAuthMiddleware
from app.services.control_plane_service import control_plane_service

try:
    from mcp.server.fastmcp import Context, FastMCP
except ImportError:  # pragma: no cover - exercised before optional dependency is installed.
    Context = Any
    FastMCP = None  # type: ignore[assignment,misc]


def create_mcp_server() -> Any | None:
    if FastMCP is None:
        return None
    server = FastMCP("WG Free Mesh", streamable_http_path="/")
    _register_resources(server)
    _register_read_tools(server)
    _register_write_tools(server)
    return server


def mcp_http_app(server: Any | None) -> ASGIApp | None:
    if server is None:
        return None
    return McpBearerAuthMiddleware(server.streamable_http_app())


@asynccontextmanager
async def mcp_session_lifespan(server: Any | None):
    if server is None:
        yield
        return
    async with server.session_manager.run():
        yield


def _register_resources(server: Any) -> None:
    @server.resource("wfm://system/status")
    def system_status_resource() -> dict[str, object]:
        return operations.read_result(
            "system_status",
            "Read system status resource",
            control_plane_service.system_status,
        )

    @server.resource("wfm://configs")
    def configs_resource() -> list[dict[str, object]]:
        return operations.read_result(
            "configs",
            "Read config list resource",
            operations.list_configs,
        )


def _register_read_tools(server: Any) -> None:
    @server.tool()
    def read_system_status() -> dict[str, object]:
        """Read the current system projection and MQTT deployment/runtime status."""
        return operations.read_result("read_system_status", "Read system status", control_plane_service.system_status)

    @server.tool()
    def read_configs() -> list[dict[str, object]]:
        """Read all Mesh configurations."""
        return operations.read_result("read_configs", "Read config list", operations.list_configs)

    @server.tool()
    def read_config(config_id: str) -> dict[str, object]:
        """Read one Mesh configuration."""
        return operations.read_result("read_config", f"Read config {config_id}", lambda: operations.get_config(config_id))

    @server.tool()
    def read_config_overview(config_id: str) -> dict[str, object]:
        """Read a configuration overview with nodes, runtime projection, and validation context."""
        return operations.read_result(
            "read_config_overview",
            f"Read config overview {config_id}",
            lambda: operations.get_config_overview(config_id),
        )

    @server.tool()
    def read_nodes(config_id: str) -> list[dict[str, object]]:
        """Read nodes in one Mesh configuration."""
        return operations.read_result("read_nodes", f"Read nodes for {config_id}", lambda: operations.list_nodes(config_id))

    @server.tool()
    def read_node_workspace(config_id: str, node_id: str) -> dict[str, object]:
        """Read the node workspace used by the control console."""
        return operations.read_result(
            "read_node_workspace",
            f"Read node workspace {config_id}/{node_id}",
            lambda: operations.get_node_workspace(config_id, node_id),
        )

    @server.tool()
    def read_mesh_workspace(config_id: str, node_id: str) -> dict[str, object]:
        """Read Mesh connections and validation for one node."""
        return operations.read_result(
            "read_mesh_workspace",
            f"Read Mesh workspace {config_id}/{node_id}",
            lambda: operations.get_mesh_workspace(config_id, node_id),
        )

    @server.tool()
    def read_mesh_validation(config_id: str) -> dict[str, object]:
        """Validate a Mesh topology without modifying it."""
        return operations.read_result(
            "read_mesh_validation",
            f"Validate Mesh {config_id}",
            lambda: operations.validate_mesh(config_id),
        )

    @server.tool()
    def read_endpoint_status(config_id: str, node_id: str) -> dict[str, object]:
        """Read endpoint status, client state, and config state for one dynamic endpoint."""
        return operations.read_result(
            "read_endpoint_status",
            f"Read endpoint status {config_id}/{node_id}",
            lambda: operations.get_endpoint_status(config_id, node_id),
        )

    @server.tool()
    def read_endpoint_logs(config_id: str, node_id: str) -> list[dict[str, object]]:
        """Read endpoint control logs."""
        return operations.read_result(
            "read_endpoint_logs",
            f"Read endpoint logs {config_id}/{node_id}",
            lambda: operations.list_endpoint_logs(config_id, node_id),
        )

    @server.tool()
    def read_port_forward_rules(config_id: str) -> list[dict[str, object]]:
        """Read port-forward rules managed by WG Free Mesh."""
        return operations.read_result(
            "read_port_forward_rules",
            f"Read port forward rules {config_id}",
            lambda: operations.list_port_forward_rules(config_id),
        )

    @server.tool()
    def read_snapshots() -> list[dict[str, object]]:
        """Read encrypted snapshot metadata."""
        return operations.read_result("read_snapshots", "Read snapshot list", operations.list_snapshots)

    @server.tool()
    def read_sync_status(config_id: str) -> list[dict[str, object]]:
        """Read sync status for all nodes in one configuration."""
        return operations.read_result(
            "read_sync_status",
            f"Read sync status {config_id}",
            lambda: operations.get_sync_status(config_id),
        )

    @server.tool()
    def read_node_sync_status(config_id: str, node_id: str) -> dict[str, object]:
        """Read sync status for one node."""
        return operations.read_result(
            "read_node_sync_status",
            f"Read node sync status {config_id}/{node_id}",
            lambda: operations.get_node_sync_status(config_id, node_id),
        )

    @server.tool()
    def read_wg_preview(config_id: str, node_id: str) -> dict[str, object]:
        """Read the generated WireGuard or AmneziaWG config preview for one node."""
        return operations.read_result(
            "read_wg_preview",
            f"Read generated config preview {config_id}/{node_id}",
            lambda: operations.get_wg_preview(config_id, node_id),
        )

    @server.tool()
    def read_client_download_options() -> dict[str, object]:
        """Read supported client artifact build options."""
        return operations.read_result(
            "read_client_download_options",
            "Read client download options",
            operations.get_download_options,
        )


def _register_write_tools(server: Any) -> None:
    @server.tool()
    async def write_create_config(ctx: Context, payload: dict[str, object]) -> dict[str, object]:
        """Create one Mesh configuration after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_config",
            summary="Create a Mesh configuration",
            impact="A new configuration and derived sync state will be created.",
            writer=lambda: operations.create_config(payload),
        )

    @server.tool()
    async def write_update_config(ctx: Context, config_id: str, payload: dict[str, object]) -> dict[str, object]:
        """Update one Mesh configuration after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_update_config",
            summary=f"Update config {config_id}",
            impact="Configuration and affected node sync state can change.",
            writer=lambda: operations.update_config(config_id, payload),
        )

    @server.tool()
    async def write_delete_config(ctx: Context, config_id: str) -> dict[str, object]:
        """Delete one Mesh configuration after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_config",
            summary=f"Delete config {config_id}",
            impact="The configuration, nodes, Mesh links, and related managed state will be removed.",
            writer=lambda: operations.delete_config(config_id),
        )

    @server.tool()
    async def write_create_node(ctx: Context, config_id: str, payload: dict[str, object]) -> dict[str, object]:
        """Create one node after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_node",
            summary=f"Create node in config {config_id}",
            impact="A node and derived configuration state will be created.",
            writer=lambda: operations.create_node(config_id, payload),
        )

    @server.tool()
    async def write_update_node(ctx: Context, node_id: str, payload: dict[str, object]) -> dict[str, object]:
        """Update one node after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_update_node",
            summary=f"Update node {node_id}",
            impact="Node identity, lifecycle hooks, addressing, or generated configs can change.",
            writer=lambda: operations.update_node(node_id, payload),
        )

    @server.tool()
    async def write_delete_node(ctx: Context, node_id: str) -> dict[str, object]:
        """Delete one node after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_node",
            summary=f"Delete node {node_id}",
            impact="The node and its managed Mesh relationships will be removed.",
            writer=lambda: operations.delete_node(node_id),
        )

    @server.tool()
    async def write_create_tag(ctx: Context, config_id: str, tag: str) -> dict[str, object]:
        """Create one configuration tag after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_tag",
            summary=f"Create tag {tag} in {config_id}",
            impact="The tag catalog for the configuration will change.",
            writer=lambda: operations.create_tag(config_id, tag),
        )

    @server.tool()
    async def write_apply_tag(ctx: Context, config_id: str, tag: str, node_ids: list[str]) -> list[dict[str, object]]:
        """Apply a tag to nodes after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_apply_tag",
            summary=f"Apply tag {tag} in {config_id}",
            impact="Selected node metadata and overviews will change.",
            writer=lambda: operations.apply_tag(config_id, tag, node_ids),
        )

    @server.tool()
    async def write_delete_tag(ctx: Context, config_id: str, tag: str) -> dict[str, object]:
        """Delete a configuration tag after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_tag",
            summary=f"Delete tag {tag} from {config_id}",
            impact="The tag will be removed from the configuration and its nodes.",
            writer=lambda: operations.delete_tag(config_id, tag),
        )

    @server.tool()
    async def write_create_peer_link_group(ctx: Context, config_id: str, payload: dict[str, object]) -> list[dict[str, object]]:
        """Create a Mesh peer-link group after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_peer_link_group",
            summary=f"Create peer link group in {config_id}",
            impact="Generated configuration state for affected nodes will change.",
            writer=lambda: operations.create_peer_link_group(config_id, payload),
        )

    @server.tool()
    async def write_update_peer_link_group(ctx: Context, group_id: str, payload: dict[str, object]) -> list[dict[str, object]]:
        """Update a Mesh peer-link group after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_update_peer_link_group",
            summary=f"Update peer link group {group_id}",
            impact="Routing, endpoint selection, and generated configuration state can change.",
            writer=lambda: operations.update_peer_link_group(group_id, payload),
        )

    @server.tool()
    async def write_delete_peer_link_group(ctx: Context, group_id: str) -> dict[str, object]:
        """Delete a Mesh peer-link group after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_peer_link_group",
            summary=f"Delete peer link group {group_id}",
            impact="Mesh connectivity for affected nodes will change.",
            writer=lambda: operations.delete_peer_link_group(group_id),
        )

    @server.tool()
    async def write_quick_generate_mesh(ctx: Context, config_id: str, payload: dict[str, object]) -> dict[str, object]:
        """Replace generated Mesh links for a quick-networking mode after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_quick_generate_mesh",
            summary=f"Regenerate quick Mesh for {config_id}",
            impact="Existing Mesh pairs under this configuration are deleted and regenerated.",
            writer=lambda: operations.quick_generate_mesh(config_id, payload),
        )

    @server.tool()
    async def write_sync_node(ctx: Context, config_id: str, node_id: str) -> dict[str, object]:
        """Sync one node and push staged config when eligible after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_sync_node",
            summary=f"Sync node {config_id}/{node_id}",
            impact="Staged configuration can be published to an online client.",
            writer=lambda: operations.sync_node(config_id, node_id),
        )

    @server.tool()
    async def write_sync_all(ctx: Context, config_id: str) -> dict[str, object]:
        """Sync all nodes in one configuration after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_sync_all",
            summary=f"Sync all nodes in {config_id}",
            impact="Multiple staged configurations can be published to online clients.",
            writer=lambda: operations.sync_all(config_id),
        )

    @server.tool()
    async def write_endpoint_control(ctx: Context, config_id: str, node_id: str, action: str) -> dict[str, object]:
        """Send start, stop, push_config, or wg_show to one endpoint after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_endpoint_control",
            summary=f"Send endpoint action {action} to {config_id}/{node_id}",
            impact="The remote client can execute a control action over MQTT.",
            writer=lambda: operations.endpoint_control(config_id, node_id, action),
        )

    @server.tool()
    async def write_probe_endpoints(ctx: Context, config_id: str, node_ids: list[str]) -> dict[str, object]:
        """Probe selected dynamic endpoints after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_probe_endpoints",
            summary=f"Probe endpoints in {config_id}",
            impact="The server will send detect messages over MQTT and runtime status can change.",
            writer=lambda: operations.probe_endpoints(config_id, node_ids),
        )

    @server.tool()
    async def write_create_bind_command(ctx: Context, config_id: str, node_id: str, server_url: str) -> dict[str, object]:
        """Create a one-time client bind command after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_bind_command",
            summary=f"Create bind command for {config_id}/{node_id}",
            impact="A one-time bind token will be minted for the node.",
            writer=lambda: operations.create_bind_command(config_id, node_id, server_url),
        )

    @server.tool()
    async def write_reset_client(ctx: Context, config_id: str, node_id: str) -> dict[str, object]:
        """Reset one node client state after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_reset_client",
            summary=f"Reset client for {config_id}/{node_id}",
            impact="Stored client credentials are reset and the MQTT client is disconnected when available.",
            writer=lambda: operations.reset_client(config_id, node_id),
        )

    @server.tool()
    async def write_create_port_forward_rule(ctx: Context, config_id: str, payload: dict[str, object]) -> dict[str, object]:
        """Create a managed port-forward rule after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_port_forward_rule",
            summary=f"Create port forward rule in {config_id}",
            impact="Managed lifecycle hooks on the destination endpoint will change.",
            writer=lambda: operations.create_port_forward_rule(config_id, payload),
        )

    @server.tool()
    async def write_set_port_forward_rule_enabled(ctx: Context, rule_id: str, enabled: bool) -> dict[str, object]:
        """Enable or disable a managed port-forward rule after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_set_port_forward_rule_enabled",
            summary=f"Set port forward rule {rule_id} enabled={enabled}",
            impact="Managed lifecycle hooks on the destination endpoint will change.",
            writer=lambda: operations.set_port_forward_rule_enabled(rule_id, enabled),
        )

    @server.tool()
    async def write_delete_port_forward_rule(ctx: Context, rule_id: str) -> dict[str, object]:
        """Delete a managed port-forward rule after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_port_forward_rule",
            summary=f"Delete port forward rule {rule_id}",
            impact="Managed lifecycle hooks on the destination endpoint will change.",
            writer=lambda: operations.delete_port_forward_rule(rule_id),
        )

    @server.tool()
    async def write_build_client_artifact(ctx: Context, source: str, goos: str, goarch: str) -> dict[str, object]:
        """Build or fetch a client download artifact after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_build_client_artifact",
            summary=f"Build client artifact {goos}/{goarch} from {source}",
            impact="A client download artifact can be generated in the backend artifact store.",
            writer=lambda: operations.build_client_artifact(source, goos, goarch),
        )

    @server.tool()
    async def write_create_config_bulk_package(ctx: Context, config_id: str, node_ids: list[str]) -> dict[str, object]:
        """Create a bulk config download package after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_config_bulk_package",
            summary=f"Create bulk config package for {config_id}",
            impact="A new bulk download package replaces the previous temporary package.",
            writer=lambda: operations.create_config_bulk_package(config_id, node_ids),
        )

    @server.tool()
    async def write_create_snapshot(ctx: Context, note: str, password: str) -> dict[str, object]:
        """Create an encrypted snapshot after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_snapshot",
            summary="Create encrypted application snapshot",
            impact="An encrypted snapshot file will be written using the supplied administrator password.",
            writer=lambda: operations.create_snapshot(note, password),
        )

    @server.tool()
    async def write_restore_snapshot(ctx: Context, snapshot_id: str, password: str) -> dict[str, object]:
        """Restore an encrypted snapshot after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_restore_snapshot",
            summary=f"Restore snapshot {snapshot_id}",
            impact="Current application data will be replaced by snapshot data after decrypting it.",
            writer=lambda: operations.restore_snapshot(snapshot_id, password),
        )

    @server.tool()
    async def write_delete_snapshot(ctx: Context, snapshot_id: str) -> dict[str, object]:
        """Delete a snapshot after user confirmation."""
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_snapshot",
            summary=f"Delete snapshot {snapshot_id}",
            impact="The encrypted snapshot file and its database record will be removed.",
            writer=lambda: operations.delete_snapshot(snapshot_id),
        )
