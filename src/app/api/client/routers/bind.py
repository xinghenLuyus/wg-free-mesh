from __future__ import annotations

import secrets
from typing import Any, cast

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.core.responses import ApiResponse, ok
from app.domain.models import Config, Node
from app.data.repositories.naming import node_config_interface_name
from app.services.control_plane_service import control_plane_service
from app.services.emqx_service import emqx_service
from app.services.mqtt_auth_service import mqtt_auth_service

router = APIRouter(tags=["client-bind"])


class ClientBindRequest(BaseModel):
    token: str = Field(min_length=1)
    hostname: str = ""
    platform: str = ""
    client_version: str = ""


@router.post("/bind")
async def bind_client(payload: ClientBindRequest) -> ApiResponse[dict[str, Any]]:
    if not control_plane_service.mqtt_service_enabled():
        raise AppError("MQTT_DISABLED", "MQTT services are disabled", 409)
    preview = control_plane_service.client_bind_preview(payload.token)
    config = cast(Config, preview["config"])
    node = cast(Node, preview["node"])
    password = secrets.token_urlsafe(32)
    username = mqtt_auth_service.node_username(node.id)
    client_id = mqtt_auth_service.node_client_id(node.id)

    emqx_service.ensure_client_tls_ready()
    response = emqx_service.upsert_node_user(node_id=node.id, password=password)
    if response.status_code >= 400:
        raise AppError(
            "EMQX_USER_SYNC_FAILED",
            "Failed to create MQTT credentials",
            502,
            {"status_code": response.status_code, "body": response.text},
        )

    control_plane_service.mark_client_bound(
        config.id,
        node.id,
        username=username,
        client_id=client_id,
        platform=payload.platform,
        version=payload.client_version,
        hostname=payload.hostname,
    )
    await control_plane_service.publish_runtime(config.id, node.id)
    desired = control_plane_service.read_applied_conf(config.id, node.id)
    return ok(
        {
            "profile": {
                "profile_id": f"{config.id}-{node.id}",
                "server_url": "",
                "config_id": config.id,
                "config_name": config.name,
                "node_id": node.id,
                "node_name": node.name,
                "interface_name": node_config_interface_name(config.name, node.name),
                "hostname": payload.hostname,
                "platform": payload.platform,
                "client_version": payload.client_version,
            },
            "mqtt": emqx_service.node_credentials_payload(
                config_id=config.id,
                node_id=node.id,
                password=password,
            ),
            "desired_conf": desired.get("content", ""),
        }
    )
