from pydantic import BaseModel, Field, field_validator

from app.core.validation import strip_required_text


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return strip_required_text(value, "Username")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        strip_required_text(value, "Password")
        return value


class SetupRequest(BaseModel):
    password: str = Field(min_length=6, max_length=256)
    locale: str = Field(default="zh-CN")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password is required")
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters")
        return value

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, value: str) -> str:
        locale = value.strip() or "zh-CN"
        if locale not in {"zh-CN", "en-US"}:
            raise ValueError("Unsupported locale")
        return locale


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=6, max_length=256)

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


class AuthStateRead(BaseModel):
    setup_required: bool
    authenticated: bool
    username: str
    display_name: str
    expires_at: str | None = None


class TokenSessionRead(AuthStateRead):
    access_token: str
    token_type: str = "bearer"


class DownloadTokenRead(BaseModel):
    access_token: str
    token_type: str = "download"
    expires_at: str
    download_path: str
    filename: str
