from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

from app.services.auth_service import CurrentUser, auth_service


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def require_current_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    return auth_service.require_user(_extract_bearer_token(authorization))


def optional_current_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser | None:
    return auth_service.optional_user(_extract_bearer_token(authorization))


CurrentUserDep = Annotated[CurrentUser, Depends(require_current_user)]
