from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.core.responses import ApiResponse, ok
from app.repositories.sqlite import store
from app.services.control_plane_service import control_plane_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


def _session_payload(username: str, authenticated: bool) -> dict[str, object]:
    return {
        "authenticated": authenticated,
        "username": username if authenticated else "",
        "display_name": "管理员" if authenticated else "",
    }


@router.post("/login")
def login(payload: LoginRequest, response: Response) -> ApiResponse[dict[str, object]]:
    if payload.username.strip() != "admin" or payload.password != store.read_password():
        raise AppError("AUTH_FAILED", "用户名或密码错误", 401)

    response.set_cookie("wfm_session", "admin", httponly=True, samesite="lax", secure=False)
    return ok(_session_payload("admin", True))


@router.get("/session")
def session() -> ApiResponse[dict[str, object]]:
    return ok(_session_payload("admin", True))


@router.post("/logout")
def logout(response: Response) -> ApiResponse[dict[str, object]]:
    response.delete_cookie("wfm_session")
    return ok(_session_payload("", False))


@router.post("/password")
def change_password(payload: PasswordChangeRequest) -> ApiResponse[dict[str, object]]:
    control_plane_service.update_password(payload.current_password, payload.new_password)
    return ok({"message": "密码已更新"})
