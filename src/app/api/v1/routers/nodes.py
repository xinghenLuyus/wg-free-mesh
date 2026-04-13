from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.responses import ApiResponse, ok
from app.services.control_plane_service import control_plane_service

router = APIRouter(tags=["nodes"])


class NodeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    listen_port: int | None = Field(default=None, ge=1, le=65535)
    virtual_ip: str | None = None
    mtu: int | None = Field(default=None, ge=576, le=65535)
    dns: str | None = None
    auto_sync: bool = True
    node_type: str = "dynamic"
    public_key: str | None = None
    private_key: str | None = None
    tags: list[str] = Field(default_factory=list)


class PrivateKeyRequest(BaseModel):
    private_key: str = Field(min_length=1)


class VirtualIpRequest(BaseModel):
    virtual_ip: str = Field(min_length=1)


@router.get("/configs/{config_id}/nodes")
def list_nodes(config_id: str) -> ApiResponse[list[dict[str, Any]]]:
    return ok([item.model_dump(mode="json") for item in control_plane_service.list_nodes(config_id)])


@router.post("/configs/{config_id}/nodes")
def create_node(config_id: str, payload: NodeRequest) -> ApiResponse[dict[str, Any]]:
    node = control_plane_service.create_node(config_id, payload.model_dump())
    return ok(node.model_dump(mode="json"))


@router.get("/nodes/{node_id}")
def get_node(node_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.get_node(node_id).model_dump(mode="json"))


@router.put("/nodes/{node_id}")
def update_node(node_id: str, payload: NodeRequest) -> ApiResponse[dict[str, Any]]:
    node = control_plane_service.update_node(node_id, payload.model_dump())
    return ok(node.model_dump(mode="json"))


@router.delete("/nodes/{node_id}")
def delete_node(node_id: str) -> ApiResponse[dict[str, str]]:
    control_plane_service.delete_node(node_id)
    return ok({"message": "节点已删除"})


@router.post("/configs/{config_id}/nodes/suggest-ip")
def suggest_ip(config_id: str) -> ApiResponse[dict[str, str]]:
    return ok({"ip": control_plane_service.suggest_virtual_ip(config_id)})


@router.post("/configs/{config_id}/nodes/validate-ip")
def validate_ip(config_id: str, payload: VirtualIpRequest) -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.validate_virtual_ip(config_id, payload.virtual_ip))


@router.post("/nodes/keys/generate")
def generate_keys() -> ApiResponse[dict[str, str]]:
    return ok(control_plane_service.create_keys())


@router.post("/nodes/keys/derive-public")
def derive_public(payload: PrivateKeyRequest) -> ApiResponse[dict[str, str]]:
    return ok(control_plane_service.derive_public_key(payload.private_key))
