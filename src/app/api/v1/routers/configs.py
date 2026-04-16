from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.responses import ApiResponse, ok
from app.services.control_plane_service import control_plane_service

router = APIRouter(prefix="/configs", tags=["configs"])


class ConfigCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    description: str = ""
    enabled: bool = True
    virtual_subnet: str = "10.66.0.0/24"
    default_listen_port: int = Field(default=51820, ge=1, le=65535)
    default_mtu: int | None = Field(default=None, ge=576, le=65535)
    default_dns: str | None = None
    auto_sync: bool = True


class ConfigUpdateRequest(ConfigCreateRequest):
    pass


@router.get("")
def list_configs() -> ApiResponse[list[dict[str, Any]]]:
    return ok([item.model_dump(mode="json") for item in control_plane_service.list_configs()])


@router.post("")
async def create_config(payload: ConfigCreateRequest) -> ApiResponse[dict[str, Any]]:
    config = control_plane_service.create_config(payload.model_dump())
    await control_plane_service.publish_configs()
    await control_plane_service.publish_config_overview(config.id)
    await control_plane_service.publish_system_status()
    return ok(config.model_dump(mode="json"))


@router.get("/{config_id}")
def get_config(config_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.get_config(config_id).model_dump(mode="json"))


@router.put("/{config_id}")
async def update_config(config_id: str, payload: ConfigUpdateRequest) -> ApiResponse[dict[str, Any]]:
    config = control_plane_service.update_config(config_id, payload.model_dump())
    await control_plane_service.publish_configs()
    await control_plane_service.publish_config_overview(config_id)
    await control_plane_service.publish_system_status()
    return ok(config.model_dump(mode="json"))


@router.delete("/{config_id}")
async def delete_config(config_id: str) -> ApiResponse[dict[str, str]]:
    control_plane_service.delete_config(config_id)
    await control_plane_service.publish_configs()
    await control_plane_service.publish_system_status()
    return ok({"message": "配置已删除"})


@router.get("/{config_id}/overview")
def config_overview(config_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.config_overview(config_id))
