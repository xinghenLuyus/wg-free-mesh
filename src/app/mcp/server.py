from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from starlette.types import ASGIApp

from app.mcp import catalog, operations
from app.mcp.access import McpBearerAuthMiddleware
from app.mcp.schemas import (
    McpClientArtifactPayload,
    McpConfigBulkPackagePayload,
    McpConfigPayload,
    McpNodePayload,
    McpPeerLinkGroupPayload,
    McpPortForwardRulePayload,
    McpQuickMeshPayload,
    SnapshotExportSelection,
)
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
    @server.resource("wfm://help/overview")
    def help_overview_resource() -> dict[str, object]:
        return operations.read_result(
            "help_overview",
            "Read MCP system overview resource",
            catalog.overview,
        )

    @server.resource("wfm://help/tool-index")
    def help_tool_index_resource() -> dict[str, object]:
        return operations.read_result(
            "help_tool_index",
            "Read MCP tool index resource",
            catalog.tool_index,
        )

    @server.resource("wfm://help/workflows")
    def help_workflows_resource() -> dict[str, object]:
        return operations.read_result(
            "help_workflows",
            "Read MCP workflow examples resource",
            catalog.workflows,
        )

    @server.resource("wfm://schema/payloads")
    def schema_payloads_resource() -> dict[str, object]:
        return operations.read_result(
            "schema_payloads",
            "Read MCP payload schema guidance resource",
            catalog.schemas,
        )

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
        """Read global WFM status.

        Use this first when an AI agent needs deployment health, node counts, online counts,
        topology validity, sync issue summaries, and MQTT service state. Read-only; no state changes.
        """
        return operations.read_result("read_system_status", "Read system status", control_plane_service.system_status)

    @server.tool()
    def read_configs() -> list[dict[str, object]]:
        """List all Mesh configurations.

        Use this to discover config_id values before reading an overview or making changes.
        Returns summary counts and topology flags. Read-only.
        """
        return operations.read_result("read_configs", "Read config list", operations.list_configs)

    @server.tool()
    def read_config(config_id: str) -> dict[str, object]:
        """Read one Mesh configuration object by id.

        Use this when only configuration-level fields are needed. For page-grade context,
        prefer read_config_overview. Read-only.
        """
        return operations.read_result("read_config", f"Read config {config_id}", lambda: operations.get_config(config_id))

    @server.tool()
    def read_config_overview(config_id: str) -> dict[str, object]:
        """Read the main configuration overview projection.

        Use this before editing a config, creating nodes, generating Mesh links, or diagnosing
        topology issues. It returns config details, nodes, runtime projection, sync state,
        and topology validation context. Read-only.
        """
        return operations.read_result(
            "read_config_overview",
            f"Read config overview {config_id}",
            lambda: operations.get_config_overview(config_id),
        )

    @server.tool()
    def read_nodes(config_id: str) -> list[dict[str, object]]:
        """List endpoints in one Mesh configuration.

        Use this to pick node_id values for Mesh, endpoint, sync, and port-forward tools.
        Read-only.
        """
        return operations.read_result("read_nodes", f"Read nodes for {config_id}", lambda: operations.list_nodes(config_id))

    @server.tool()
    def read_node_workspace(config_id: str, node_id: str) -> dict[str, object]:
        """Read a node detail workspace.

        Use this when an AI agent needs the same context as the node settings/control page:
        node data, tags, config, and endpoint status when applicable. Read-only.
        """
        return operations.read_result(
            "read_node_workspace",
            f"Read node workspace {config_id}/{node_id}",
            lambda: operations.get_node_workspace(config_id, node_id),
        )

    @server.tool()
    def read_mesh_workspace(config_id: str, node_id: str) -> dict[str, object]:
        """Read Mesh links from one node's perspective.

        Use this before creating, editing, enabling, disabling, or deleting peer-link groups.
        It returns bidirectional link cards and validation status. Read-only.
        """
        return operations.read_result(
            "read_mesh_workspace",
            f"Read Mesh workspace {config_id}/{node_id}",
            lambda: operations.get_mesh_workspace(config_id, node_id),
        )

    @server.tool()
    def read_mesh_validation(config_id: str) -> dict[str, object]:
        """Validate a Mesh topology without modifying it.

        Use this to check whether generated configs and sync are blocked by topology errors.
        Read-only.
        """
        return operations.read_result(
            "read_mesh_validation",
            f"Validate Mesh {config_id}",
            lambda: operations.validate_mesh(config_id),
        )

    @server.tool()
    def read_endpoint_status(config_id: str, node_id: str) -> dict[str, object]:
        """Read runtime status for one dynamic endpoint.

        Use this to diagnose online/offline state, client binding state, MQTT state,
        WireGuard/AmneziaWG runtime state, and staged/confirmed config state. Read-only.
        """
        return operations.read_result(
            "read_endpoint_status",
            f"Read endpoint status {config_id}/{node_id}",
            lambda: operations.get_endpoint_status(config_id, node_id),
        )

    @server.tool()
    def read_endpoint_logs(config_id: str, node_id: str) -> list[dict[str, object]]:
        """Read endpoint control logs.

        Use this after write_endpoint_control, write_sync_node, or status diagnosis to see
        command acknowledgements, failures, and command output summaries. Read-only.
        """
        return operations.read_result(
            "read_endpoint_logs",
            f"Read endpoint logs {config_id}/{node_id}",
            lambda: operations.list_endpoint_logs(config_id, node_id),
        )

    @server.tool()
    def read_port_forward_rules(config_id: str) -> list[dict[str, object]]:
        """Read WFM-managed port-forward rules.

        Use this before creating, enabling, disabling, or deleting port-forward rules.
        These rules are managed by WFM and appear as generated lifecycle hooks. Read-only.
        """
        return operations.read_result(
            "read_port_forward_rules",
            f"Read port forward rules {config_id}",
            lambda: operations.list_port_forward_rules(config_id),
        )

    @server.tool()
    def read_snapshots() -> list[dict[str, object]]:
        """Read encrypted snapshot metadata.

        Use this to find snapshot_id values before restore or delete. Does not expose
        encrypted payload contents or administrator password. Read-only.
        """
        return operations.read_result("read_snapshots", "Read snapshot list", operations.list_snapshots)

    @server.tool()
    def read_sync_status(config_id: str) -> list[dict[str, object]]:
        """Read sync status for all nodes in one configuration.

        Use this to understand desired/staged/confirmed config versions and whether auto-sync
        produced issues. Read-only.
        """
        return operations.read_result(
            "read_sync_status",
            f"Read sync status {config_id}",
            lambda: operations.get_sync_status(config_id),
        )

    @server.tool()
    def read_node_sync_status(config_id: str, node_id: str) -> dict[str, object]:
        """Read sync status for one node.

        Use this to diagnose why one endpoint has pending, stale, or blocked config state.
        Read-only.
        """
        return operations.read_result(
            "read_node_sync_status",
            f"Read node sync status {config_id}/{node_id}",
            lambda: operations.get_node_sync_status(config_id, node_id),
        )

    @server.tool()
    def read_wg_preview(config_id: str, node_id: str) -> dict[str, object]:
        """Read generated WireGuard or AmneziaWG config text for one node.

        Use this to inspect what would be staged/downloaded for the endpoint. It does not
        sync or push the config. Read-only.
        """
        return operations.read_result(
            "read_wg_preview",
            f"Read generated config preview {config_id}/{node_id}",
            lambda: operations.get_wg_preview(config_id, node_id),
        )

    @server.tool()
    def read_client_download_options() -> dict[str, object]:
        """Read supported client artifact build options.

        Use this before write_build_client_artifact to choose source, OS, and architecture.
        Read-only.
        """
        return operations.read_result(
            "read_client_download_options",
            "Read client download options",
            operations.get_download_options,
        )


def _register_write_tools(server: Any) -> None:
    @server.tool()
    async def write_create_config(ctx: Context, payload: McpConfigPayload) -> dict[str, object]:
        """Create one Mesh configuration.

        Use when the user explicitly asks to create a new network/config. Requires a write
        token and MCP confirmation. Side effects: creates database records and refreshes derived state.
        Prefer read_configs first to avoid duplicate names.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_config",
            summary="Create a Mesh configuration",
            impact="A new configuration and derived sync state will be created.",
            writer=lambda: operations.create_config(payload.model_dump()),
        )

    @server.tool()
    async def write_update_config(ctx: Context, config_id: str, payload: McpConfigPayload) -> dict[str, object]:
        """Update one Mesh configuration.

        Use for configuration settings, default node behavior, and protocol changes.
        Requires a write token and MCP confirmation. Side effects: updates config, may recalculate
        affected node sync state, and may clear or create AWG fields according to protocol rules.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_update_config",
            summary=f"Update config {config_id}",
            impact="Configuration and affected node sync state can change.",
            writer=lambda: operations.update_config(config_id, payload.model_dump()),
        )

    @server.tool()
    async def write_delete_config(ctx: Context, config_id: str) -> dict[str, object]:
        """Delete one Mesh configuration.

        Use only when the user explicitly requests deletion. Requires a write token and MCP
        confirmation. High impact: removes the configuration, nodes, Mesh links, sync state,
        and related managed state.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_config",
            summary=f"Delete config {config_id}",
            impact="The configuration, nodes, Mesh links, and related managed state will be removed.",
            writer=lambda: operations.delete_config(config_id),
        )

    @server.tool()
    async def write_create_node(ctx: Context, config_id: str, payload: McpNodePayload) -> dict[str, object]:
        """Create one endpoint in a configuration.

        Use after reading the target config. Requires a write token and MCP confirmation.
        Side effects: creates node data, generated key material when needed, and derived sync state.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_node",
            summary=f"Create node in config {config_id}",
            impact="A node and derived configuration state will be created.",
            writer=lambda: operations.create_node(config_id, payload.model_dump()),
        )

    @server.tool()
    async def write_update_node(ctx: Context, node_id: str, payload: McpNodePayload) -> dict[str, object]:
        """Update one endpoint.

        Use for addresses, virtual IP, tags, enabled state, lifecycle hooks, and AWG local
        parameters. Requires a write token and MCP confirmation. Side effects can affect Mesh
        validation, generated configs, and MQTT authorization for dynamic nodes.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_update_node",
            summary=f"Update node {node_id}",
            impact="Node identity, lifecycle hooks, addressing, or generated configs can change.",
            writer=lambda: operations.update_node(node_id, payload.model_dump()),
        )

    @server.tool()
    async def write_delete_node(ctx: Context, node_id: str) -> dict[str, object]:
        """Delete one endpoint.

        Use only on explicit user request. Requires a write token and MCP confirmation.
        Side effects: removes the node and managed Mesh relationships; dynamic MQTT user may be revoked.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_node",
            summary=f"Delete node {node_id}",
            impact="The node and its managed Mesh relationships will be removed.",
            writer=lambda: operations.delete_node(node_id),
        )

    @server.tool()
    async def write_create_tag(ctx: Context, config_id: str, tag: str) -> dict[str, object]:
        """Create one tag in a configuration.

        Use when organizing nodes. Requires a write token and MCP confirmation.
        Side effects: changes tag catalog only.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_tag",
            summary=f"Create tag {tag} in {config_id}",
            impact="The tag catalog for the configuration will change.",
            writer=lambda: operations.create_tag(config_id, tag),
        )

    @server.tool()
    async def write_apply_tag(ctx: Context, config_id: str, tag: str, node_ids: list[str]) -> list[dict[str, object]]:
        """Apply an existing or new tag to selected nodes.

        Use after read_nodes so node_ids are known. Requires a write token and MCP confirmation.
        Side effects: changes node metadata and overview projection.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_apply_tag",
            summary=f"Apply tag {tag} in {config_id}",
            impact="Selected node metadata and overviews will change.",
            writer=lambda: operations.apply_tag(config_id, tag, node_ids),
        )

    @server.tool()
    async def write_delete_tag(ctx: Context, config_id: str, tag: str) -> dict[str, object]:
        """Delete a tag from a configuration and remove it from nodes.

        Requires a write token and MCP confirmation. Side effects: changes tag catalog and node metadata.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_tag",
            summary=f"Delete tag {tag} from {config_id}",
            impact="The tag will be removed from the configuration and its nodes.",
            writer=lambda: operations.delete_tag(config_id, tag),
        )

    @server.tool()
    async def write_create_peer_link_group(ctx: Context, config_id: str, payload: McpPeerLinkGroupPayload) -> list[dict[str, object]]:
        """Create one bidirectional Mesh peer-link group.

        Use after read_mesh_workspace or read_config_overview. Requires a write token and MCP
        confirmation. Side effects: creates forward/reverse peer links and refreshes generated
        config state for affected nodes.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_peer_link_group",
            summary=f"Create peer link group in {config_id}",
            impact="Generated configuration state for affected nodes will change.",
            writer=lambda: operations.create_peer_link_group(config_id, payload.model_dump()),
        )

    @server.tool()
    async def write_update_peer_link_group(ctx: Context, group_id: str, payload: McpPeerLinkGroupPayload) -> list[dict[str, object]]:
        """Update one bidirectional Mesh peer-link group.

        Use to change AllowedIPs, endpoint mode, keepalive, PSK, notes, or enabled state.
        Requires a write token and MCP confirmation. Side effects: routing and generated configs
        for affected nodes can change.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_update_peer_link_group",
            summary=f"Update peer link group {group_id}",
            impact="Routing, endpoint selection, and generated configuration state can change.",
            writer=lambda: operations.update_peer_link_group(group_id, payload.model_dump()),
        )

    @server.tool()
    async def write_delete_peer_link_group(ctx: Context, group_id: str) -> dict[str, object]:
        """Delete one bidirectional Mesh peer-link group.

        Requires a write token and MCP confirmation. Side effects: removes Mesh connectivity
        for affected nodes and refreshes generated configs.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_peer_link_group",
            summary=f"Delete peer link group {group_id}",
            impact="Mesh connectivity for affected nodes will change.",
            writer=lambda: operations.delete_peer_link_group(group_id),
        )

    @server.tool()
    async def write_quick_generate_mesh(ctx: Context, config_id: str, payload: McpQuickMeshPayload) -> dict[str, object]:
        """Delete and regenerate Mesh links using a quick-networking mode.

        Use only when the user wants WFM to rebuild all Mesh pairs in a configuration.
        Requires a write token and MCP confirmation. High impact: existing Mesh pairs are deleted
        and replaced by hub_spoke, full_mesh, or free_mesh output.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_quick_generate_mesh",
            summary=f"Regenerate quick Mesh for {config_id}",
            impact="Existing Mesh pairs under this configuration are deleted and regenerated.",
            writer=lambda: operations.quick_generate_mesh(config_id, payload.model_dump()),
        )

    @server.tool()
    async def write_sync_node(ctx: Context, config_id: str, node_id: str) -> dict[str, object]:
        """Sync one node and push staged config when eligible.

        Use after inspecting read_node_sync_status or read_wg_preview. Requires a write token
        and MCP confirmation. Side effects: staged config can be published to an online dynamic client.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_sync_node",
            summary=f"Sync node {config_id}/{node_id}",
            impact="Staged configuration can be published to an online client.",
            writer=lambda: operations.sync_node(config_id, node_id),
        )

    @server.tool()
    async def write_sync_all(ctx: Context, config_id: str) -> dict[str, object]:
        """Sync all eligible nodes in one configuration.

        Use when the user wants configuration changes propagated broadly. Requires a write token
        and MCP confirmation. Side effects: multiple staged configs can be published to online clients.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_sync_all",
            summary=f"Sync all nodes in {config_id}",
            impact="Multiple staged configurations can be published to online clients.",
            writer=lambda: operations.sync_all(config_id),
        )

    @server.tool()
    async def write_endpoint_control(ctx: Context, config_id: str, node_id: str, action: str) -> dict[str, object]:
        """Send a runtime control action to one dynamic endpoint.

        action must be start, stop, push_config, or wg_show. Requires a write token and MCP
        confirmation. Side effects: remote client can start/stop tunnels, apply config, or run diagnostics.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_endpoint_control",
            summary=f"Send endpoint action {action} to {config_id}/{node_id}",
            impact="The remote client can execute a control action over MQTT.",
            writer=lambda: operations.endpoint_control(config_id, node_id, action),
        )

    @server.tool()
    async def write_probe_endpoints(ctx: Context, config_id: str, node_ids: list[str]) -> dict[str, object]:
        """Probe selected dynamic endpoints over MQTT.

        Use to refresh runtime presence/status for selected nodes or all nodes when node_ids is empty.
        Requires a write token and MCP confirmation. Side effects: runtime status can change.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_probe_endpoints",
            summary=f"Probe endpoints in {config_id}",
            impact="The server will send detect messages over MQTT and runtime status can change.",
            writer=lambda: operations.probe_endpoints(config_id, node_ids),
        )

    @server.tool()
    async def write_create_bind_command(ctx: Context, config_id: str, node_id: str, server_url: str) -> dict[str, object]:
        """Create a one-time client bind command for a dynamic endpoint.

        Use when the user wants to initialize or re-bind an endpoint client. Requires a write token
        and MCP confirmation. Side effects: mints a short-lived bind token for the node.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_bind_command",
            summary=f"Create bind command for {config_id}/{node_id}",
            impact="A one-time bind token will be minted for the node.",
            writer=lambda: operations.create_bind_command(config_id, node_id, server_url),
        )

    @server.tool()
    async def write_reset_client(ctx: Context, config_id: str, node_id: str) -> dict[str, object]:
        """Reset one dynamic endpoint client state.

        Use when the user wants to invalidate existing client binding. Requires a write token
        and MCP confirmation. Side effects: clears client state and revokes/disconnects MQTT access when available.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_reset_client",
            summary=f"Reset client for {config_id}/{node_id}",
            impact="Stored client credentials are reset and the MQTT client is disconnected when available.",
            writer=lambda: operations.reset_client(config_id, node_id),
        )

    @server.tool()
    async def write_create_port_forward_rule(ctx: Context, config_id: str, payload: McpPortForwardRulePayload) -> dict[str, object]:
        """Create one WFM-managed port-forward rule.

        Use after read_nodes and read_port_forward_rules. Requires a write token and MCP confirmation.
        Side effects: creates a managed rule and changes generated lifecycle hooks on the to_node.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_port_forward_rule",
            summary=f"Create port forward rule in {config_id}",
            impact="Managed lifecycle hooks on the destination endpoint will change.",
            writer=lambda: operations.create_port_forward_rule(config_id, payload.model_dump()),
        )

    @server.tool()
    async def write_set_port_forward_rule_enabled(ctx: Context, rule_id: str, enabled: bool) -> dict[str, object]:
        """Enable or disable one managed port-forward rule.

        Requires a write token and MCP confirmation. Side effects: generated lifecycle hooks on
        the rule destination node are updated.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_set_port_forward_rule_enabled",
            summary=f"Set port forward rule {rule_id} enabled={enabled}",
            impact="Managed lifecycle hooks on the destination endpoint will change.",
            writer=lambda: operations.set_port_forward_rule_enabled(rule_id, enabled),
        )

    @server.tool()
    async def write_delete_port_forward_rule(ctx: Context, rule_id: str) -> dict[str, object]:
        """Delete one managed port-forward rule.

        Requires a write token and MCP confirmation. Side effects: removes the rule and generated
        lifecycle hooks from the destination node.
        """
        return await operations.confirmed_write(
            ctx,
            target_name="write_delete_port_forward_rule",
            summary=f"Delete port forward rule {rule_id}",
            impact="Managed lifecycle hooks on the destination endpoint will change.",
            writer=lambda: operations.delete_port_forward_rule(rule_id),
        )

    @server.tool()
    async def write_build_client_artifact(ctx: Context, source: str = "", goos: str = "", goarch: str = "") -> dict[str, object]:
        """Build or fetch a client download artifact.

        Use after read_client_download_options. Requires a write token and MCP confirmation.
        Parameters: source is local_build or github_release; goos is windows, linux, or darwin;
        goarch is amd64, arm64, or 386. The 386 architecture is Windows-only.
        Side effects: may generate a zip artifact in the backend artifact store.
        """
        selection = await _resolve_client_artifact_selection(ctx, source, goos, goarch)
        return await operations.confirmed_write(
            ctx,
            target_name="write_build_client_artifact",
            summary=f"Build client artifact {selection.goos}/{selection.goarch} from {selection.source}",
            impact="A client download artifact can be generated in the backend artifact store.",
            writer=lambda: operations.build_client_artifact(selection.source, selection.goos, selection.goarch),
        )

    @server.tool()
    async def write_create_config_bulk_package(ctx: Context, config_id: str = "", node_ids: list[str] | None = None) -> dict[str, object]:
        """Create a bulk staged-config download package.

        Use when the user wants a zip of selected nodes' staged configs. Requires a write token
        and MCP confirmation. Side effects: creates a new temporary bulk package and replaces
        the previous package in that artifact area.
        """
        selection = await _resolve_config_bulk_selection(ctx, config_id, node_ids or [])
        return await operations.confirmed_write(
            ctx,
            target_name="write_create_config_bulk_package",
            summary=f"Create bulk config package for {selection.config_id}",
            impact="A new bulk download package replaces the previous temporary package.",
            writer=lambda: operations.create_config_bulk_package(selection.config_id, selection.node_ids),
        )

    @server.tool()
    async def write_export_snapshot(ctx: Context, snapshot_id: str = "") -> dict[str, object]:
        """Create a short-lived download URL for one encrypted snapshot export.

        Use after read_snapshots when the user wants to download an existing snapshot.
        Requires a write token and MCP confirmation because exported snapshots contain sensitive
        application data. The returned URL contains a 5-minute token scoped only to this snapshot file.
        MCP intentionally does not create, import, restore, or delete snapshots.
        """
        target_snapshot_id = await _resolve_snapshot_export_selection(ctx, snapshot_id)
        return await operations.confirmed_write(
            ctx,
            target_name="write_export_snapshot",
            summary=f"Export snapshot {target_snapshot_id}",
            impact="A 5-minute URL for this encrypted snapshot export will be created.",
            writer=lambda: operations.export_snapshot(target_snapshot_id),
        )


async def _resolve_client_artifact_selection(ctx: Context, source: str, goos: str, goarch: str) -> McpClientArtifactPayload:
    if source and goos and goarch:
        return McpClientArtifactPayload(source=source, goos=goos, goarch=goarch)
    response = await ctx.elicit(
        message="Select the WG Free Mesh client artifact target. Use read_client_download_options if you need all supported options.",
        schema=McpClientArtifactPayload,
    )
    if response.action != "accept" or response.data is None:
        raise PermissionError("Client artifact target was not provided")
    return response.data


async def _resolve_config_bulk_selection(ctx: Context, config_id: str, node_ids: list[str]) -> McpConfigBulkPackagePayload:
    if config_id and node_ids:
        return McpConfigBulkPackagePayload(config_id=config_id, node_ids=node_ids)
    response = await ctx.elicit(
        message="Provide the configuration id and node ids to include in the bulk config package. Use read_configs/read_nodes first if needed.",
        schema=McpConfigBulkPackagePayload,
    )
    if response.action != "accept" or response.data is None:
        raise PermissionError("Config bulk package selection was not provided")
    return response.data


async def _resolve_snapshot_export_selection(ctx: Context, snapshot_id: str) -> str:
    if snapshot_id.strip():
        return snapshot_id.strip()
    response = await ctx.elicit(
        message="Provide the snapshot_id to export. Use read_snapshots first if needed.",
        schema=SnapshotExportSelection,
    )
    if response.action != "accept" or response.data is None:
        raise PermissionError("Snapshot export selection was not provided")
    return response.data.snapshot_id
