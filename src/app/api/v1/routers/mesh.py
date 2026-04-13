from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.responses import ApiResponse, ok
from app.services.control_plane_service import control_plane_service

router = APIRouter(tags=["mesh"])


class PeerLinkGroupRequest(BaseModel):
    local_node_id: str = Field(min_length=1)
    peer_node_id: str = Field(min_length=1)
    allowed_ips_forward: str = Field(min_length=1)
    allowed_ips_reverse: str = Field(min_length=1)
    persistent_keepalive: int | None = Field(default=None, ge=0, le=65535)
    preshared_key: str | None = None
    endpoint_mode: str = "auto"
    endpoint_ref_family: str | None = "ipv4"
    endpoint_manual_host: str | None = None
    endpoint_port_mode: str = "ref_peer_listen_port"
    endpoint_manual_port: int | None = Field(default=None, ge=1, le=65535)
    notes: str = ""
    enabled: bool = True


class WgPreviewResponse(BaseModel):
    node_id: str
    node_name: str
    content: str
    sha256: str


@router.get("/configs/{config_id}/peer-links")
def list_peer_links(config_id: str) -> ApiResponse[list[dict[str, Any]]]:
    return ok([item.model_dump(mode="json") for item in control_plane_service.list_peer_links(config_id)])


@router.post("/configs/{config_id}/peer-links")
def create_peer_link_group(config_id: str, payload: PeerLinkGroupRequest) -> ApiResponse[list[dict[str, Any]]]:
    items = control_plane_service.create_peer_link_group(config_id, payload.model_dump())
    return ok([item.model_dump(mode="json") for item in items])


@router.put("/peer-links/{group_id}")
def update_peer_link_group(group_id: str, payload: PeerLinkGroupRequest) -> ApiResponse[list[dict[str, Any]]]:
    items = control_plane_service.update_peer_link_group(group_id, payload.model_dump())
    return ok([item.model_dump(mode="json") for item in items])


@router.delete("/peer-links/{group_id}")
def delete_peer_link_group(group_id: str) -> ApiResponse[dict[str, str]]:
    control_plane_service.delete_peer_link_group(group_id)
    return ok({"message": "链路组已删除"})


@router.post("/configs/{config_id}/mesh/validate")
def validate_mesh(config_id: str) -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.validate_mesh(config_id))


@router.get("/configs/{config_id}/nodes/{node_id}/wg-preview")
def wg_preview(config_id: str, node_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.build_wg_preview(config_id, node_id))
