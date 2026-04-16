from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path
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


class TagRead(BaseModel):
    name: str
    count: int


class ApplyTagRequest(BaseModel):
    tag: str = Field(min_length=1, max_length=64)
    node_ids: list[str] = Field(default_factory=list)


class CreateTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class NodeTagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


@router.get("/configs/{config_id}/nodes")
def list_nodes(config_id: str) -> ApiResponse[list[dict[str, Any]]]:
    return ok([item.model_dump(mode="json") for item in control_plane_service.list_nodes(config_id)])


@router.post("/configs/{config_id}/nodes")
async def create_node(config_id: str, payload: NodeRequest) -> ApiResponse[dict[str, Any]]:
    node = control_plane_service.create_node(config_id, payload.model_dump())
    await control_plane_service.publish_configs()
    await control_plane_service.publish_config_overview(config_id)
    await control_plane_service.publish_node_workspace(config_id, node.id)
    await control_plane_service.publish_node_apply(config_id, node.id)
    await control_plane_service.publish_mesh_workspace(config_id, node.id)
    await control_plane_service.publish_system_status()
    return ok(node.model_dump(mode="json"))


@router.get("/nodes/{node_id}")
def get_node(node_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.get_node(node_id).model_dump(mode="json"))


@router.put("/nodes/{node_id}")
async def update_node(node_id: str, payload: NodeRequest) -> ApiResponse[dict[str, Any]]:
    node = control_plane_service.update_node(node_id, payload.model_dump())
    await control_plane_service.publish_configs()
    await control_plane_service.publish_config_overview(node.config_id)
    await control_plane_service.publish_node_workspace(node.config_id, node.id)
    await control_plane_service.publish_node_apply(node.config_id, node.id)
    await control_plane_service.publish_mesh_workspace(node.config_id, node.id)
    await control_plane_service.publish_system_status()
    return ok(node.model_dump(mode="json"))


@router.get("/configs/{config_id}/tags")
def list_tags(config_id: str) -> ApiResponse[list[TagRead]]:
    return ok([TagRead.model_validate(item) for item in control_plane_service.list_tags(config_id)])


@router.post("/configs/{config_id}/tags")
async def create_tag(config_id: str, payload: CreateTagRequest) -> ApiResponse[TagRead]:
    tag = TagRead.model_validate(control_plane_service.create_tag(config_id, payload.name))
    await control_plane_service.publish_config_overview(config_id)
    return ok(tag)


@router.post("/configs/{config_id}/tags/apply")
async def apply_tag_to_nodes(config_id: str, payload: ApplyTagRequest) -> ApiResponse[list[dict[str, Any]]]:
    nodes = control_plane_service.apply_tag_to_nodes(config_id, payload.tag, payload.node_ids)
    await control_plane_service.publish_config_overview(config_id)
    for node in nodes:
        await control_plane_service.publish_node_workspace(config_id, node.id)
    return ok([item.model_dump(mode="json") for item in nodes])


@router.delete("/configs/{config_id}/tags/{tag_name}")
async def delete_tag_from_config(
    config_id: str,
    tag_name: Annotated[str, Path(min_length=1, max_length=64)],
) -> ApiResponse[dict[str, int | str]]:
    removed_count = control_plane_service.delete_tag_from_config(config_id, tag_name)
    await control_plane_service.publish_config_overview(config_id)
    return ok({"message": "标签已删除", "removed_count": removed_count})


@router.put("/nodes/{node_id}/tags")
async def replace_node_tags(node_id: str, payload: NodeTagsRequest) -> ApiResponse[dict[str, Any]]:
    node = control_plane_service.replace_node_tags(node_id, payload.tags)
    await control_plane_service.publish_config_overview(node.config_id)
    await control_plane_service.publish_node_workspace(node.config_id, node.id)
    return ok(node.model_dump(mode="json"))


@router.delete("/nodes/{node_id}/tags/{tag_name}")
async def remove_tag_from_node(
    node_id: str,
    tag_name: Annotated[str, Path(min_length=1, max_length=64)],
) -> ApiResponse[dict[str, Any]]:
    node = control_plane_service.remove_tag_from_node(node_id, tag_name)
    await control_plane_service.publish_config_overview(node.config_id)
    await control_plane_service.publish_node_workspace(node.config_id, node.id)
    return ok(node.model_dump(mode="json"))


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str) -> ApiResponse[dict[str, str]]:
    node = control_plane_service.get_node(node_id)
    control_plane_service.delete_node(node_id)
    await control_plane_service.publish_configs()
    await control_plane_service.publish_config_overview(node.config_id)
    await control_plane_service.publish_system_status()
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
