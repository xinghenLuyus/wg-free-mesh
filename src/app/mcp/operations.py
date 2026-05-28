from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast
from urllib.parse import urlencode

from pydantic import BaseModel, Field

from app.api.v1.routers.configs import ConfigCreateRequest, ConfigUpdateRequest
from app.api.v1.routers.mesh import PeerLinkGroupRequest, QuickMeshGenerateRequest
from app.api.v1.routers.nodes import NodeRequest
from app.api.v1.routers.tools import PortForwardRuleRequest
from app.core.config import settings
from app.core.errors import AppError
from app.mcp.access import McpAccessGrant, current_mcp_grant
from app.services.control_plane_service import control_plane_service
from app.services.auth_service import auth_service
from app.services.download_tools_service import download_tools_service


class WriteConfirmation(BaseModel):
    confirmed: bool = Field(description="Confirm this write operation after reviewing its impact.")


def read_result(target_name: str, summary: str, reader: Callable[[], Any]) -> Any:
    grant = current_mcp_grant()
    try:
        result = reader()
    except Exception as exc:
        _audit(grant, target_name=target_name, summary=summary, result="failed", error=exc)
        raise
    _audit(grant, target_name=target_name, summary=summary, result="succeeded")
    return result


async def confirmed_write(
    ctx: Any,
    *,
    target_name: str,
    summary: str,
    impact: str,
    writer: Callable[[], Awaitable[Any]],
) -> Any:
    grant = current_mcp_grant()
    if grant.permission != "write":
        error = PermissionError("MCP write token is required")
        _audit(
            grant,
            target_name=target_name,
            summary=summary,
            impact=impact,
            confirmation_required=True,
            confirmation_result="not_allowed",
            result="rejected",
            error=error,
        )
        raise error

    confirmation_result: Literal["accepted", "rejected", "unsupported"] = "unsupported"
    try:
        response = await ctx.elicit(
            message=f"{summary}\nImpact: {impact}\nAllow this WG Free Mesh write operation?",
            schema=WriteConfirmation,
        )
        if response.action != "accept" or response.data is None or not response.data.confirmed:
            confirmation_result = "rejected"
            raise PermissionError("MCP write operation was not confirmed")
        confirmation_result = "accepted"
        value = await writer()
    except Exception as exc:
        _audit(
            grant,
            target_name=target_name,
            summary=summary,
            impact=impact,
            confirmation_required=True,
            confirmation_result=confirmation_result,
            result="failed",
            error=exc,
        )
        raise
    _audit(
        grant,
        target_name=target_name,
        summary=summary,
        impact=impact,
        confirmation_required=True,
        confirmation_result=confirmation_result,
        result="succeeded",
    )
    return value


def list_configs() -> list[dict[str, Any]]:
    return control_plane_service.configs_payload()


def get_config(config_id: str) -> dict[str, Any]:
    return control_plane_service.get_config(config_id).model_dump(mode="json")


def get_config_overview(config_id: str) -> dict[str, Any]:
    return control_plane_service.config_overview(config_id)


def list_nodes(config_id: str) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in control_plane_service.list_nodes(config_id)]


def get_node_workspace(config_id: str, node_id: str) -> dict[str, Any]:
    return control_plane_service.node_workspace(config_id, node_id)


def get_mesh_workspace(config_id: str, node_id: str) -> dict[str, Any]:
    return control_plane_service.mesh_workspace(config_id, node_id)


def validate_mesh(config_id: str) -> dict[str, object]:
    return control_plane_service.validate_mesh(config_id)


def get_endpoint_status(config_id: str, node_id: str) -> dict[str, Any]:
    return control_plane_service.endpoint_status(config_id, node_id)


def list_endpoint_logs(config_id: str, node_id: str) -> list[dict[str, Any]]:
    return control_plane_service.endpoint_logs(config_id, node_id)


def list_port_forward_rules(config_id: str) -> list[dict[str, object]]:
    return control_plane_service.list_port_forward_rules(config_id)


def list_snapshots() -> list[dict[str, Any]]:
    return control_plane_service.snapshots_payload()


def get_sync_status(config_id: str) -> list[dict[str, Any]]:
    return control_plane_service.sync_status_for_config(config_id)


def get_node_sync_status(config_id: str, node_id: str) -> dict[str, Any]:
    return control_plane_service.sync_status_for_node(config_id, node_id)


def get_wg_preview(config_id: str, node_id: str) -> dict[str, Any]:
    return control_plane_service.build_wg_preview(config_id, node_id)


def get_download_options() -> dict[str, object]:
    return download_tools_service.client_options()


async def create_config(payload: dict[str, object]) -> dict[str, Any]:
    validated = ConfigCreateRequest.model_validate(payload)
    config = control_plane_service.create_config(validated.model_dump())
    await control_plane_service.schedule_config_refresh(
        config.id,
        control_plane_service.plan_for_config_change(config.id),
    )
    return config.model_dump(mode="json")


async def update_config(config_id: str, payload: dict[str, object]) -> dict[str, Any]:
    validated = ConfigUpdateRequest.model_validate(payload)
    result = control_plane_service.update_config(config_id, validated.model_dump())
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_config_change(
            config_id,
            [str(item) for item in result.get("affected_node_ids", [])],
        ),
    )
    return result


async def delete_config(config_id: str) -> dict[str, str]:
    control_plane_service.delete_config(config_id)
    await control_plane_service.publish_plan(
        control_plane_service.plan_for_config_change(config_id, include_overview=False)
    )
    return {"message": "Config deleted"}


async def create_node(config_id: str, payload: dict[str, object]) -> dict[str, Any]:
    validated = NodeRequest.model_validate(payload)
    node = control_plane_service.create_node(config_id, validated.model_dump())
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_node_change(config_id, [node.id]),
    )
    return node.model_dump(mode="json")


async def update_node(node_id: str, payload: dict[str, object]) -> dict[str, Any]:
    validated = NodeRequest.model_validate(payload)
    result = control_plane_service.update_node(node_id, validated.model_dump())
    config_id = str(result["config_id"])
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_node_change(
            config_id,
            [str(item) for item in result.get("affected_node_ids", [result["id"]])],
        ),
    )
    return result


async def delete_node(node_id: str) -> dict[str, str]:
    node = control_plane_service.get_node(node_id)
    control_plane_service.delete_node(node_id)
    await control_plane_service.schedule_config_refresh(
        node.config_id,
        control_plane_service.plan_for_node_change(node.config_id, []),
    )
    return {"message": "Node deleted"}


async def create_tag(config_id: str, tag: str) -> dict[str, object]:
    result = control_plane_service.create_tag(config_id, tag)
    await control_plane_service.publish_config_overview(config_id)
    return result


async def apply_tag(config_id: str, tag: str, node_ids: list[str]) -> list[dict[str, Any]]:
    nodes = control_plane_service.apply_tag_to_nodes(config_id, tag, node_ids)
    await control_plane_service.publish_config_overview(config_id)
    for node in nodes:
        await control_plane_service.publish_node_workspace(config_id, node.id)
    return [item.model_dump(mode="json") for item in nodes]


async def delete_tag(config_id: str, tag: str) -> dict[str, object]:
    removed_count = control_plane_service.delete_tag_from_config(config_id, tag)
    await control_plane_service.publish_config_overview(config_id)
    return {"message": "Tag deleted", "removed_count": removed_count}


async def create_peer_link_group(config_id: str, payload: dict[str, object]) -> list[dict[str, Any]]:
    validated = PeerLinkGroupRequest.model_validate(payload)
    links = control_plane_service.create_peer_link_group(config_id, validated.model_dump())
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_mesh_change(
            config_id,
            {validated.forward.local_node_id, validated.reverse.local_node_id},
        ),
    )
    return [item.model_dump(mode="json") for item in links]


async def update_peer_link_group(group_id: str, payload: dict[str, object]) -> list[dict[str, Any]]:
    validated = PeerLinkGroupRequest.model_validate(payload)
    links = control_plane_service.update_peer_link_group(group_id, validated.model_dump())
    config_id = control_plane_service.get_node(validated.forward.local_node_id).config_id
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_mesh_change(
            config_id,
            {validated.forward.local_node_id, validated.reverse.local_node_id},
        ),
    )
    return [item.model_dump(mode="json") for item in links]


async def delete_peer_link_group(group_id: str) -> dict[str, str]:
    config_id, affected = control_plane_service.peer_link_group_context(group_id)
    control_plane_service.delete_peer_link_group(group_id)
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_mesh_change(config_id, affected),
    )
    return {"message": "Peer link group deleted"}


async def quick_generate_mesh(config_id: str, payload: dict[str, object]) -> dict[str, object]:
    validated = QuickMeshGenerateRequest.model_validate(payload)
    result = control_plane_service.quick_generate_mesh(config_id, validated.model_dump())
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_mesh_change(
            config_id,
            set(cast(list[str], result["affected_node_ids"])),
        ),
    )
    return result


async def create_port_forward_rule(config_id: str, payload: dict[str, object]) -> dict[str, object]:
    validated = PortForwardRuleRequest.model_validate(payload)
    result = control_plane_service.create_port_forward_rule(config_id, validated.model_dump())
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_node_change(config_id, {str(result["to_node_id"])}),
    )
    return result


async def set_port_forward_rule_enabled(rule_id: str, enabled: bool) -> dict[str, object]:
    result = control_plane_service.update_port_forward_rule_enabled(rule_id, enabled)
    config_id = str(result["config_id"])
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_node_change(config_id, {str(result["to_node_id"])}),
    )
    return result


async def delete_port_forward_rule(rule_id: str) -> dict[str, str]:
    result = control_plane_service.delete_port_forward_rule(rule_id)
    await control_plane_service.schedule_config_refresh(
        result["config_id"],
        control_plane_service.plan_for_node_change(result["config_id"], {result["to_node_id"]}),
    )
    return {"message": "Port forward rule deleted"}


async def sync_node(config_id: str, node_id: str) -> dict[str, Any]:
    result = control_plane_service.sync_node(config_id, node_id)
    await control_plane_service.publish_pending_config_pushes(config_id, [node_id], requested_by="mcp")
    await control_plane_service.publish_node_apply(config_id, node_id)
    await control_plane_service.publish_node_workspace(config_id, node_id)
    await control_plane_service.publish_config_overview(config_id)
    await control_plane_service.publish_system_status()
    return result


async def sync_all(config_id: str) -> dict[str, Any]:
    result = control_plane_service.sync_all(config_id)
    await control_plane_service.publish_pending_config_pushes(config_id, requested_by="mcp")
    for node in control_plane_service.list_nodes(config_id):
        if node.enabled:
            await control_plane_service.publish_node_apply(config_id, node.id)
        await control_plane_service.publish_node_workspace(config_id, node.id)
    await control_plane_service.publish_config_overview(config_id)
    await control_plane_service.publish_system_status()
    return result


async def endpoint_control(config_id: str, node_id: str, action: str) -> dict[str, Any]:
    return await control_plane_service.control_action(config_id, node_id, action)


async def probe_endpoints(config_id: str, node_ids: list[str]) -> dict[str, Any]:
    return await control_plane_service.probe_batch(config_id, node_ids)


async def create_bind_command(config_id: str, node_id: str, server_url: str) -> dict[str, object]:
    return control_plane_service.create_client_bind_command(config_id, node_id, server_url)


async def reset_client(config_id: str, node_id: str) -> dict[str, object]:
    state = control_plane_service.reset_client_state(config_id, node_id)
    await control_plane_service.publish_runtime(config_id, node_id)
    return {"client_state": state}


async def build_client_artifact(source: str, goos: str, goarch: str) -> dict[str, object]:
    artifact = download_tools_service.build_client_artifact(source, goos, goarch)
    if artifact.get("download_url"):
        return artifact
    return _with_file_download_url(
        artifact,
        kind="client_artifact",
        resource_id=str(artifact["artifact_id"]),
        download_path=str(artifact["download_path"]),
    )


async def create_config_bulk_package(config_id: str, node_ids: list[str]) -> dict[str, object]:
    package = download_tools_service.create_config_bulk_package(config_id, node_ids)
    return _with_file_download_url(
        package,
        kind="config_bulk_package",
        resource_id=str(package["package_id"]),
        download_path=str(package["download_path"]),
    )


async def create_snapshot(note: str, password: str) -> dict[str, Any]:
    snapshot = control_plane_service.create_snapshot(note, password)
    await control_plane_service.publish_snapshots()
    return snapshot.model_dump(mode="json")


async def restore_snapshot(snapshot_id: str, password: str) -> dict[str, object]:
    control_plane_service.restore_snapshot(snapshot_id, password)
    recovery = await control_plane_service.recover_after_snapshot_restore()
    await control_plane_service.publish_full_state()
    return {"message": "Snapshot restored", "recovery": recovery}


async def delete_snapshot(snapshot_id: str) -> dict[str, str]:
    control_plane_service.delete_snapshot(snapshot_id)
    await control_plane_service.publish_snapshots()
    return {"message": "Snapshot deleted"}


async def export_snapshot(snapshot_id: str) -> dict[str, object]:
    path = control_plane_service.export_snapshot(snapshot_id)
    payload: dict[str, object] = {
        "kind": "snapshot_export",
        "snapshot_id": snapshot_id,
        "filename": path.name,
        "download_path": f"/api/v1/backups/export/{snapshot_id}",
    }
    return _with_file_download_url(
        payload,
        kind="snapshot_export",
        resource_id=snapshot_id,
        download_path=str(payload["download_path"]),
    )


def _with_file_download_url(
    payload: dict[str, object],
    *,
    kind: str,
    resource_id: str,
    download_path: str,
) -> dict[str, object]:
    grant = current_mcp_grant()
    token = auth_service.create_file_download_token(
        kind=kind,
        resource_id=resource_id,
        subject=f"mcp:{grant.name}",
    )
    access_token = str(token["access_token"])
    return {
        **payload,
        "kind": kind,
        "download_url": _download_url(download_path, access_token),
        "download_token_expires_at": str(token["expires_at"]),
        "token_type": "download",
    }


def _download_url(path: str, token: str) -> str:
    separator = "&" if "?" in path else "?"
    relative = f"{path}{separator}{urlencode({'download_token': token})}"
    public_origin = settings.public_origin.strip().rstrip("/")
    return f"{public_origin}{relative}" if public_origin else relative


def _audit(
    grant: McpAccessGrant,
    *,
    target_name: str,
    summary: str,
    result: str,
    impact: str = "",
    confirmation_required: bool = False,
    confirmation_result: str = "",
    error: Exception | None = None,
) -> None:
    error_code = error.code if isinstance(error, AppError) else error.__class__.__name__ if error else ""
    control_plane_service.create_mcp_audit_log(
        {
            "token_id": grant.id,
            "token_name": grant.name,
            "permission": grant.permission,
            "target_kind": "tool",
            "target_name": target_name,
            "summary": summary,
            "impact": impact,
            "confirmation_required": confirmation_required,
            "confirmation_result": confirmation_result,
            "result": result,
            "error_code": error_code,
        }
    )
