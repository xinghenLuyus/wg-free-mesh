from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from fastapi.responses import PlainTextResponse

from app.api.v1.deps import CurrentUserDep, DownloadGrantDep
from app.api.v1.routing import SessionProtectedAPIRouter
from app.core.responses import ApiResponse, ok
from app.schemas.auth import DownloadTokenRead
from app.services.control_plane_service import control_plane_service
from app.services.auth_service import auth_service

router = SessionProtectedAPIRouter(tags=["endpoints"])
download_router = APIRouter(tags=["endpoints"])


class AppliedConfRequest(BaseModel):
    content: str


class ControlRequest(BaseModel):
    action: str = Field(pattern="^(probe|start|stop|restart|wg_show|sync)$")


class ProbeBatchRequest(BaseModel):
    node_ids: list[str] = Field(default_factory=list)


@router.get("/configs/{config_id}/sync-status")
def sync_status_for_config(config_id: str) -> ApiResponse[list[dict[str, Any]]]:
    return ok(control_plane_service.sync_status_for_config(config_id))


@router.get("/configs/{config_id}/nodes/{node_id}/sync-status")
def sync_status_for_node(config_id: str, node_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.sync_status_for_node(config_id, node_id))


@router.get("/configs/{config_id}/nodes/{node_id}/applied-conf")
def read_applied_conf(config_id: str, node_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.read_applied_conf(config_id, node_id))


@router.get("/configs/{config_id}/nodes/{node_id}/download-package")
def download_package(config_id: str, node_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.download_package(config_id, node_id))


@router.post("/configs/{config_id}/nodes/{node_id}/download-token")
def create_download_token(config_id: str, node_id: str, user: CurrentUserDep) -> ApiResponse[DownloadTokenRead]:
    package = control_plane_service.download_package(config_id, node_id)
    token_payload = auth_service.create_download_token(config_id=config_id, node_id=node_id, user=user)
    return ok(
        DownloadTokenRead(
            access_token=str(token_payload["access_token"]),
            token_type=str(token_payload["token_type"]),
            expires_at=str(token_payload["expires_at"]),
            download_path=f'{package["download_path"]}?download_token={token_payload["access_token"]}',
            filename=str(package["filename"]),
        )
    )


@router.put("/configs/{config_id}/nodes/{node_id}/applied-conf")
async def save_applied_conf(config_id: str, node_id: str, payload: AppliedConfRequest) -> ApiResponse[dict[str, Any]]:
    result = control_plane_service.save_applied_conf(config_id, node_id, payload.content)
    await control_plane_service.publish_node_apply(config_id, node_id)
    await control_plane_service.publish_node_workspace(config_id, node_id)
    return ok(result)


@router.post("/configs/{config_id}/nodes/{node_id}/sync")
async def sync_node(config_id: str, node_id: str) -> ApiResponse[dict[str, Any]]:
    result = control_plane_service.sync_node(config_id, node_id)
    await control_plane_service.publish_node_apply(config_id, node_id)
    await control_plane_service.publish_node_workspace(config_id, node_id)
    await control_plane_service.publish_config_overview(config_id)
    await control_plane_service.publish_system_status()
    return ok(result)


@router.post("/configs/{config_id}/sync-all")
async def sync_all(config_id: str) -> ApiResponse[dict[str, Any]]:
    result = control_plane_service.sync_all(config_id)
    for node in control_plane_service.list_nodes(config_id):
        await control_plane_service.publish_node_apply(config_id, node.id)
        await control_plane_service.publish_node_workspace(config_id, node.id)
    await control_plane_service.publish_config_overview(config_id)
    await control_plane_service.publish_system_status()
    return ok(result)


@router.get("/configs/{config_id}/endpoint/runtime-snapshot")
def runtime_snapshot(config_id: str) -> ApiResponse[list[dict[str, Any]]]:
    return ok(control_plane_service.runtime_snapshot(config_id))


@router.get("/configs/{config_id}/nodes/{node_id}/endpoint/status")
def endpoint_status(config_id: str, node_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.endpoint_status(config_id, node_id))


@router.get("/configs/{config_id}/nodes/{node_id}/endpoint/logs")
def endpoint_logs(config_id: str, node_id: str) -> ApiResponse[list[dict[str, Any]]]:
    return ok(control_plane_service.endpoint_logs(config_id, node_id))


@router.post("/configs/{config_id}/nodes/{node_id}/endpoint/control")
async def endpoint_control(config_id: str, node_id: str, payload: ControlRequest) -> ApiResponse[dict[str, Any]]:
    return ok(await control_plane_service.control_action(config_id, node_id, payload.action))


@router.post("/configs/{config_id}/endpoint/probe-batch")
async def probe_batch(config_id: str, payload: ProbeBatchRequest) -> ApiResponse[dict[str, Any]]:
    return ok(await control_plane_service.probe_batch(config_id, payload.node_ids))


@download_router.get("/configs/{config_id}/nodes/{node_id}/download-conf")
def download_conf(config_id: str, node_id: str, _: DownloadGrantDep) -> PlainTextResponse:
    package = control_plane_service.download_package(config_id, node_id)
    response = PlainTextResponse(str(package["content"]), media_type="text/plain; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{package["filename"]}"'
    response.headers["Cache-Control"] = "no-store"
    return response
