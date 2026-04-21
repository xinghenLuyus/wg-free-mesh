from __future__ import annotations

from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel, Field, field_validator

from app.api.v1.routing import SessionProtectedAPIRouter
from app.core.validation import strip_optional_text, strip_required_text
from app.core.responses import ApiResponse, ok
from app.services.control_plane_service import control_plane_service

router = SessionProtectedAPIRouter(tags=["mesh"])


class PeerLinkDirectionRequest(BaseModel):
    local_node_id: str = Field(min_length=1)
    peer_node_id: str = Field(min_length=1)
    allowed_ips: str = Field(min_length=1)
    persistent_keepalive: int | None = Field(default=None, ge=0, le=65535)
    preshared_key: str | None = None
    endpoint_mode: str = "auto"
    endpoint_ref_family: str | None = "ipv4"
    endpoint_manual_host: str | None = None
    endpoint_port_mode: str = "ref_peer_listen_port"
    endpoint_manual_port: int | None = Field(default=None, ge=1, le=65535)
    notes: str = ""
    enabled: bool = True

    @field_validator("local_node_id")
    @classmethod
    def validate_local_node_id(cls, value: str) -> str:
        return strip_required_text(value, "Local node")

    @field_validator("peer_node_id")
    @classmethod
    def validate_peer_node_id(cls, value: str) -> str:
        return strip_required_text(value, "Peer node")

    @field_validator("allowed_ips")
    @classmethod
    def validate_allowed_ips(cls, value: str) -> str:
        return strip_required_text(value, "AllowedIPs")

    @field_validator("endpoint_manual_host", "preshared_key", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return strip_optional_text(value)

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str:
        return str(value or "").strip()


class PeerLinkGroupRequest(BaseModel):
    forward: PeerLinkDirectionRequest
    reverse: PeerLinkDirectionRequest
    preshared_key: str | None = None
    notes: str = ""
    enabled: bool = True

    @field_validator("preshared_key", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return strip_optional_text(value)

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str:
        return str(value or "").strip()


class WgPreviewResponse(BaseModel):
    node_id: str
    node_name: str
    content: str
    sha256: str


class PeerLinkDirectionDraftResponse(BaseModel):
    local_node_id: str
    peer_node_id: str
    allowed_ips: str
    persistent_keepalive: int | None
    endpoint_mode: str
    endpoint_ref_family: str
    endpoint_manual_host: str
    endpoint_port_mode: str
    endpoint_manual_port: int | None
    endpoint_summary: str
    keepalive_display: str


class PeerLinkDraftResponse(BaseModel):
    local_node: dict[str, Any]
    peer_node: dict[str, Any]
    endpoint_ref_family: str
    forward: PeerLinkDirectionDraftResponse
    reverse: PeerLinkDirectionDraftResponse
    warnings: list[str]


class MeshConnectionDirectionResponse(BaseModel):
    link_id: str
    local_node_id: str
    peer_node_id: str
    allowed_ips: str
    persistent_keepalive: int | None
    endpoint_mode: str
    endpoint_ref_family: str | None
    endpoint_manual_host: str | None
    endpoint_port_mode: str
    endpoint_manual_port: int | None
    endpoint_summary: str
    keepalive_display: str


class MeshConnectionResponse(BaseModel):
    link_group_id: str
    peer_node: dict[str, Any]
    enabled: bool
    has_preshared_key: bool
    preshared_key: str | None
    notes: str
    updated_at: str
    forward: MeshConnectionDirectionResponse
    reverse: MeshConnectionDirectionResponse | None
    integrity_status: str
    integrity_message: str


class MeshWorkspaceResponse(BaseModel):
    node: dict[str, Any]
    connections: list[MeshConnectionResponse]
    validation: dict[str, Any]


@router.get("/configs/{config_id}/peer-links")
def list_peer_links(config_id: str) -> ApiResponse[list[dict[str, Any]]]:
    return ok([item.model_dump(mode="json") for item in control_plane_service.list_peer_links(config_id)])


@router.get("/configs/{config_id}/nodes/{node_id}/mesh-workspace")
def mesh_workspace(config_id: str, node_id: str) -> ApiResponse[MeshWorkspaceResponse]:
    workspace = control_plane_service.mesh_workspace(config_id, node_id)
    return ok(MeshWorkspaceResponse.model_validate(workspace))


@router.get("/configs/{config_id}/nodes/{node_id}/peer-link-draft")
def peer_link_draft(
    config_id: str,
    node_id: str,
    peer_node_id: Annotated[str, Query(min_length=1)],
    endpoint_ref_family: Annotated[str, Query(pattern="^(ipv4|ipv6)$")] = "ipv4",
) -> ApiResponse[PeerLinkDraftResponse]:
    draft = control_plane_service.build_peer_link_draft(config_id, node_id, peer_node_id, endpoint_ref_family)
    return ok(PeerLinkDraftResponse.model_validate(draft))


@router.post("/configs/{config_id}/peer-links")
async def create_peer_link_group(config_id: str, payload: PeerLinkGroupRequest) -> ApiResponse[list[dict[str, Any]]]:
    items = control_plane_service.create_peer_link_group(config_id, payload.model_dump())
    affected = {payload.forward.local_node_id, payload.reverse.local_node_id}
    for node_id in affected:
        await control_plane_service.publish_mesh_workspace(config_id, node_id)
        await control_plane_service.publish_node_workspace(config_id, node_id)
        await control_plane_service.publish_node_apply(config_id, node_id)
    await control_plane_service.publish_config_overview(config_id)
    await control_plane_service.publish_system_status()
    return ok([item.model_dump(mode="json") for item in items])


@router.put("/peer-links/{group_id}")
async def update_peer_link_group(group_id: str, payload: PeerLinkGroupRequest) -> ApiResponse[list[dict[str, Any]]]:
    items = control_plane_service.update_peer_link_group(group_id, payload.model_dump())
    config_id = control_plane_service.get_node(payload.forward.local_node_id).config_id
    affected = {payload.forward.local_node_id, payload.reverse.local_node_id}
    for node_id in affected:
        await control_plane_service.publish_mesh_workspace(config_id, node_id)
        await control_plane_service.publish_node_workspace(config_id, node_id)
        await control_plane_service.publish_node_apply(config_id, node_id)
    await control_plane_service.publish_config_overview(config_id)
    await control_plane_service.publish_system_status()
    return ok([item.model_dump(mode="json") for item in items])


@router.delete("/peer-links/{group_id}")
async def delete_peer_link_group(group_id: str) -> ApiResponse[dict[str, str]]:
    config_id, affected = control_plane_service.peer_link_group_context(group_id)
    control_plane_service.delete_peer_link_group(group_id)
    for node_id in affected:
        await control_plane_service.publish_mesh_workspace(config_id, node_id)
        await control_plane_service.publish_node_workspace(config_id, node_id)
        await control_plane_service.publish_node_apply(config_id, node_id)
    await control_plane_service.publish_config_overview(config_id)
    await control_plane_service.publish_system_status()
    return ok({"message": "Peer link group deleted"})


@router.post("/peer-links/psk/generate")
def generate_preshared_key() -> ApiResponse[dict[str, str]]:
    return ok(control_plane_service.create_preshared_key())


@router.post("/configs/{config_id}/mesh/validate")
def validate_mesh(config_id: str) -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.validate_mesh(config_id))


@router.get("/configs/{config_id}/nodes/{node_id}/wg-preview")
def wg_preview(config_id: str, node_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.build_wg_preview(config_id, node_id))
