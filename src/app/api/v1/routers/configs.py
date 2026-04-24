from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.api.v1.routing import SessionProtectedAPIRouter
from app.core.responses import ApiResponse, ok
from app.core.validation import normalize_cidr, strip_optional_text, strip_required_text
from app.services.control_plane_service import control_plane_service

router = SessionProtectedAPIRouter(prefix="/configs", tags=["configs"])


class ConfigCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    description: str = ""
    enabled: bool = True
    virtual_subnet: str = "10.66.0.0/24"
    default_listen_port: int = Field(default=51820, ge=1, le=65535)
    default_mtu: int | None = Field(default=None, ge=576, le=65535)
    default_dns: str | None = None
    auto_sync: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return strip_required_text(value, "Name")

    @field_validator("description", "virtual_subnet", mode="before")
    @classmethod
    def normalize_text(cls, value: str | None) -> str:
        return str(value or "").strip()

    @field_validator("virtual_subnet")
    @classmethod
    def validate_virtual_subnet(cls, value: str) -> str:
        return normalize_cidr(value, "Virtual subnet")

    @field_validator("default_dns", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return strip_optional_text(value)


class ConfigUpdateRequest(ConfigCreateRequest):
    pass


@router.get("")
def list_configs() -> ApiResponse[list[dict[str, Any]]]:
    return ok([item.model_dump(mode="json") for item in control_plane_service.list_configs()])


@router.post("")
async def create_config(payload: ConfigCreateRequest) -> ApiResponse[dict[str, Any]]:
    config = control_plane_service.create_config(payload.model_dump())
    await control_plane_service.schedule_config_refresh(config.id, control_plane_service.plan_for_config_change(config.id))
    return ok(config.model_dump(mode="json"))


@router.get("/{config_id}")
def get_config(config_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.get_config(config_id).model_dump(mode="json"))


@router.put("/{config_id}")
async def update_config(config_id: str, payload: ConfigUpdateRequest) -> ApiResponse[dict[str, Any]]:
    result = control_plane_service.update_config(config_id, payload.model_dump())
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_config_change(config_id, [str(item) for item in result.get("affected_node_ids", [])])
    )
    return ok(result)


@router.delete("/{config_id}")
async def delete_config(config_id: str) -> ApiResponse[dict[str, str]]:
    control_plane_service.delete_config(config_id)
    await control_plane_service.publish_plan(
        control_plane_service.plan_for_config_change(config_id, include_overview=False)
    )
    return ok({"message": "Config deleted"})


@router.get("/{config_id}/overview")
def config_overview(config_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.config_overview(config_id))
