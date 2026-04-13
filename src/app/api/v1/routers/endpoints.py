from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.responses import ApiResponse, ok
from app.services.control_plane_service import control_plane_service

router = APIRouter(tags=["endpoints"])


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


@router.put("/configs/{config_id}/nodes/{node_id}/applied-conf")
def save_applied_conf(config_id: str, node_id: str, payload: AppliedConfRequest) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.save_applied_conf(config_id, node_id, payload.content))


@router.post("/configs/{config_id}/nodes/{node_id}/sync")
def sync_node(config_id: str, node_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.sync_node(config_id, node_id))


@router.post("/configs/{config_id}/sync-all")
def sync_all(config_id: str) -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.sync_all(config_id))


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
