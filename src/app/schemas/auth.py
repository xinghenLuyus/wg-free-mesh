from pydantic import BaseModel, Field, field_validator

from app.core.validation import strip_required_text


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return strip_required_text(value, "用户名")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        strip_required_text(value, "密码")
        return value


class SetupRequest(BaseModel):
    password: str = Field(min_length=6, max_length=256)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("密码不能为空")
        if len(value) < 6:
            raise ValueError("密码不能少于 6 个字符")
        return value


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=6, max_length=256)

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
