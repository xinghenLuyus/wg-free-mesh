from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.api.v1.routing import SessionProtectedAPIRouter
from app.core.responses import ApiResponse, ok
from app.core.validation import strip_optional_text, strip_required_text
from app.schemas.auth import TokenSessionRead
from app.services.control_plane_service import control_plane_service
from app.services.auth_service import auth_service

router = SessionProtectedAPIRouter(prefix="/settings", tags=["settings"])


class MqttSettingsRequest(BaseModel):
    host: str = ""
    port: int = Field(default=8883, ge=1, le=65535)
    tls: bool = True

    @field_validator("host", mode="before")
    @classmethod
    def normalize_host(cls, value: str | None) -> str:
        return strip_optional_text(value) or ""


class PasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, value: str) -> str:
        strip_required_text(value, "Current password")
        return value

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("New password is required")
        if len(value) < 6:
            raise ValueError("New password must be at least 6 characters")
        return value


class UiSettingsRequest(BaseModel):
    locale: str = "zh-CN"
    theme_mode: str = "system"

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, value: str) -> str:
        locale = value.strip() or "zh-CN"
        if locale not in {"zh-CN", "en-US"}:
            raise ValueError("Unsupported locale")
        return locale

    @field_validator("theme_mode")
    @classmethod
    def validate_theme_mode(cls, value: str) -> str:
        theme_mode = value.strip() or "system"
        if theme_mode not in {"system", "light", "dark"}:
            raise ValueError("Unsupported theme mode")
        return theme_mode


def _ui_settings_payload() -> dict[str, str]:
    locale = control_plane_service.read_setting("ui_locale") or "zh-CN"
    if locale not in {"zh-CN", "en-US"}:
        locale = "zh-CN"
    theme_mode = control_plane_service.read_setting("ui_theme_mode") or "system"
    if theme_mode not in {"system", "light", "dark"}:
        theme_mode = "system"
    return {"locale": locale, "theme_mode": theme_mode}


@router.get("/ui")
def ui_settings() -> ApiResponse[dict[str, str]]:
    return ok(_ui_settings_payload())


@router.put("/ui")
def update_ui_settings(payload: UiSettingsRequest) -> ApiResponse[dict[str, str]]:
    control_plane_service.write_setting("ui_locale", payload.locale)
    control_plane_service.write_setting("ui_theme_mode", payload.theme_mode)
    return ok(_ui_settings_payload())


@router.get("/mqtt")
def mqtt_settings() -> ApiResponse[dict[str, Any]]:
    return ok(control_plane_service.mqtt_settings())


@router.put("/mqtt")
async def update_mqtt_settings(payload: MqttSettingsRequest) -> ApiResponse[dict[str, Any]]:
    from app.services.mqtt_ingress_service import mqtt_ingress_service

    result = control_plane_service.update_mqtt_settings(payload.model_dump())
    await mqtt_ingress_service.reconcile()
    await control_plane_service.publish_mqtt_settings()
    await control_plane_service.publish_system_status()
    return ok(result)


@router.post("/mqtt/test")
async def test_mqtt(payload: MqttSettingsRequest) -> ApiResponse[dict[str, Any]]:
    return ok(await control_plane_service.test_mqtt_settings(payload.model_dump()))


@router.post("/password")
def update_password(payload: PasswordRequest) -> ApiResponse[TokenSessionRead]:
    return ok(TokenSessionRead.model_validate(auth_service.change_password(payload.current_password, payload.new_password)))
