from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.responses import ApiResponse, ok
from app.services.control_plane_service import control_plane_service
from app.services.auth_service import auth_service

router = APIRouter(prefix="/settings", tags=["settings"])


class MqttSettingsRequest(BaseModel):
    host: str = ""
    port: int = Field(default=8883, ge=1, le=65535)
    tls: bool = True
    username: str = ""
    password: str = ""


class PasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


@router.get("/mqtt")
def mqtt_settings() -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.mqtt_settings())


@router.put("/mqtt")
async def update_mqtt_settings(payload: MqttSettingsRequest) -> ApiResponse[dict[str, Any]]:
    result = control_plane_service.update_mqtt_settings(payload.model_dump())
    await control_plane_service.publish_mqtt_settings()
    return ok(result)


@router.post("/mqtt/test")
def test_mqtt(payload: MqttSettingsRequest) -> ApiResponse[dict[str, Any]]:
    return ok(
        {
            "success": bool(payload.host.strip()),
            "message": "已保存测试参数，真实 MQTT 连通性留在客户端阶段恢复",
            "latency_ms": 0,
        }
    )


@router.post("/password")
def update_password(payload: PasswordRequest) -> ApiResponse[dict[str, Any]]:
    auth_service.change_password(payload.current_password, payload.new_password)
    return ok({"message": "密码已更新"})
