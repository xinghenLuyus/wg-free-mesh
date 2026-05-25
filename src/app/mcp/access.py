from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Literal

from starlette.types import ASGIApp, Receive, Scope, Send

from app.services.control_plane_service import control_plane_service


@dataclass(frozen=True)
class McpAccessGrant:
    id: str
    name: str
    permission: Literal["read", "write"]


_current_grant: ContextVar[McpAccessGrant | None] = ContextVar("wfm_mcp_access_grant", default=None)


def current_mcp_grant() -> McpAccessGrant:
    grant = _current_grant.get()
    if grant is None:
        raise PermissionError("MCP access token is required")
    return grant


class McpBearerAuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        grant = self._grant(scope)
        if grant is None:
            await self._unauthorized(send)
            return
        context_token: Token[McpAccessGrant | None] = _current_grant.set(grant)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_grant.reset(context_token)

    @staticmethod
    def _grant(scope: Scope) -> McpAccessGrant | None:
        raw_headers = scope.get("headers") or []
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in raw_headers}
        authorization = headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        payload = control_plane_service.find_active_mcp_token(token.strip())
        if payload is None:
            return None
        permission = str(payload["permission"])
        if permission not in {"read", "write"}:
            return None
        return McpAccessGrant(
            id=str(payload["id"]),
            name=str(payload["name"]),
            permission=permission,
        )

    @staticmethod
    async def _unauthorized(send: Send) -> None:
        body = b'{"error":"MCP access token is missing, expired, revoked, or invalid"}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
