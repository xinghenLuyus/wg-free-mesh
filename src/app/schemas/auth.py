from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class SetupRequest(BaseModel):
    password: str = Field(min_length=6, max_length=256)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=6, max_length=256)


class AuthStateRead(BaseModel):
    setup_required: bool
    authenticated: bool
    username: str
    display_name: str
    expires_at: str | None = None


class TokenSessionRead(AuthStateRead):
    access_token: str
    token_type: str = "bearer"
