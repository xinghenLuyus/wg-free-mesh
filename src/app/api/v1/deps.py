from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Query

from app.services.auth_service import CurrentUser, DownloadGrant, auth_service


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


def require_download_grant(
    config_id: str,
    node_id: str,
    download_token: Annotated[str | None, Query()] = None,
) -> DownloadGrant:
    return auth_service.require_download_grant(download_token, config_id=config_id, node_id=node_id)


def require_file_download_or_user(
    kind: str,
    resource_id: str,
    authorization: str | None,
    download_token: str | None,
) -> None:
    user = auth_service.optional_user(_extract_bearer_token(authorization))
    if user is not None:
        return
    auth_service.require_file_download_grant(download_token, kind=kind, resource_id=resource_id)


CurrentUserDep = Annotated[CurrentUser, Depends(require_current_user)]
DownloadGrantDep = Annotated[DownloadGrant, Depends(require_download_grant)]
