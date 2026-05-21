from __future__ import annotations

from typing import Annotated, Any

from fastapi import Body, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.api.v1.routing import SessionProtectedAPIRouter
from app.core.responses import ApiResponse, ok
from app.core.validation import strip_required_text
from app.services.control_plane_service import control_plane_service
from app.services.download_tools_service import download_tools_service

router = SessionProtectedAPIRouter(prefix="/tools", tags=["tools"])


class PortForwardRuleRequest(BaseModel):
    from_node_id: str = Field(min_length=1)
    from_port: int = Field(ge=1, le=65535)
    to_node_id: str = Field(min_length=1)
    to_port: int = Field(ge=1, le=65535)
    to_platform: str = Field(pattern="^(linux|darwin)$")
    protocol: str = Field(default="tcp", pattern="^(tcp|udp|all)$")

    @field_validator("from_node_id", "to_node_id")
    @classmethod
    def normalize_node_id(cls, value: str) -> str:
        return strip_required_text(value, "Node")


class PortForwardRuleEnabledRequest(BaseModel):
    enabled: bool


@router.get("/download/client-options")
def client_download_options() -> ApiResponse[dict[str, object]]:
    return ok(download_tools_service.client_options())


@router.post("/download/client-artifacts/build")
def build_client_artifact(payload: Annotated[dict[str, Any], Body()]) -> ApiResponse[dict[str, object]]:
    return ok(
        download_tools_service.build_client_artifact(
            str(payload.get("source") or ""),
            str(payload.get("goos") or ""),
            str(payload.get("goarch") or ""),
        )
    )


@router.get("/download/client-artifacts/{artifact_id}")
def download_client_artifact(artifact_id: str) -> FileResponse:
    path, filename = download_tools_service.client_artifact_file(artifact_id)
    return FileResponse(path=str(path), filename=filename, media_type="application/zip")


@router.get("/download/config-bulk/options")
def config_bulk_options(config_id: Annotated[str | None, Query()] = None) -> ApiResponse[dict[str, object]]:
    return ok(download_tools_service.config_bulk_options(config_id))


@router.post("/download/config-bulk/package")
def create_config_bulk_package(payload: Annotated[dict[str, Any], Body()]) -> ApiResponse[dict[str, object]]:
    node_ids = payload.get("node_ids")
    return ok(
        download_tools_service.create_config_bulk_package(
            str(payload.get("config_id") or ""),
            [str(item) for item in node_ids] if isinstance(node_ids, list) else [],
        )
    )


@router.get("/download/config-bulk/{package_id}")
def download_config_bulk_package(package_id: str) -> FileResponse:
    path = download_tools_service.config_bulk_file(package_id)
    return FileResponse(path=str(path), filename=path.name, media_type="application/zip")


@router.get("/port-forwards/configs/{config_id}")
def list_port_forward_rules(config_id: str) -> ApiResponse[list[dict[str, object]]]:
    return ok(control_plane_service.list_port_forward_rules(config_id))


@router.post("/port-forwards/configs/{config_id}")
async def create_port_forward_rule(config_id: str, payload: PortForwardRuleRequest) -> ApiResponse[dict[str, object]]:
    result = control_plane_service.create_port_forward_rule(config_id, payload.model_dump())
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_node_change(config_id, {str(result["to_node_id"])}),
    )
    return ok(result)


@router.delete("/port-forwards/{rule_id}")
async def delete_port_forward_rule(rule_id: str) -> ApiResponse[dict[str, str]]:
    result = control_plane_service.delete_port_forward_rule(rule_id)
    await control_plane_service.schedule_config_refresh(
        result["config_id"],
        control_plane_service.plan_for_node_change(result["config_id"], {result["to_node_id"]}),
    )
    return ok({"message": "Port forward rule deleted"})


@router.put("/port-forwards/{rule_id}/enabled")
async def update_port_forward_rule_enabled(rule_id: str, payload: PortForwardRuleEnabledRequest) -> ApiResponse[dict[str, object]]:
    result = control_plane_service.update_port_forward_rule_enabled(rule_id, payload.enabled)
    config_id = str(result["config_id"])
    to_node_id = str(result["to_node_id"])
    await control_plane_service.schedule_config_refresh(
        config_id,
        control_plane_service.plan_for_node_change(config_id, {to_node_id}),
    )
    return ok(result)
