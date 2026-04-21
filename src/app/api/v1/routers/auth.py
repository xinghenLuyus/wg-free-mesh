from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header

from app.api.v1.deps import CurrentUserDep
from app.core.responses import ApiResponse, ok
from app.schemas.auth import AuthStateRead, LoginRequest, PasswordChangeRequest, SetupRequest, TokenSessionRead
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


@router.get("/state")
def state(authorization: Annotated[str | None, Header()] = None) -> ApiResponse[AuthStateRead]:
    return ok(AuthStateRead.model_validate(auth_service.auth_state(_extract_bearer_token(authorization))))


@router.post("/setup")
def setup(payload: SetupRequest) -> ApiResponse[TokenSessionRead]:
    return ok(TokenSessionRead.model_validate(auth_service.setup(payload.password, payload.locale)))


@router.post("/login")
def login(payload: LoginRequest) -> ApiResponse[TokenSessionRead]:
    return ok(TokenSessionRead.model_validate(auth_service.login(payload.username, payload.password)))


@router.get("/session")
def session(authorization: Annotated[str | None, Header()] = None) -> ApiResponse[AuthStateRead]:
    return ok(AuthStateRead.model_validate(auth_service.auth_state(_extract_bearer_token(authorization))))


@router.post("/logout")
def logout() -> ApiResponse[dict[str, object]]:
    return ok({"message": "Logged out"})


@router.post("/password")
def change_password(payload: PasswordChangeRequest, _: CurrentUserDep) -> ApiResponse[TokenSessionRead]:
    return ok(TokenSessionRead.model_validate(auth_service.change_password(payload.current_password, payload.new_password)))
