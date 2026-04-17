from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.api.v1.routing import SessionProtectedAPIRouter
from app.core.responses import ApiResponse, ok
from app.core.validation import strip_optional_text, strip_required_text
from app.services.control_plane_service import control_plane_service
from app.services.auth_service import auth_service

router = SessionProtectedAPIRouter(prefix="/settings", tags=["settings"])


class MqttSettingsRequest(BaseModel):
    host: str = ""
    port: int = Field(default=8883, ge=1, le=65535)
    tls: bool = True
    username: str = ""
    password: str = ""

    @field_validator("host", "username", "password", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str:
        return strip_optional_text(value) or ""


class PasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, value: str) -> str:
        strip_required_text(value, "当前密码")
        return value

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("新密码不能为空")
        if len(value) < 6:
            raise ValueError("新密码不能少于 6 个字符")
        return value


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
