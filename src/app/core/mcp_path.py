from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class McpPathNormalizeMiddleware:
    """Normalize /mcp to /mcp/ so Starlette mount routing reaches FastMCP."""

    def __init__(self, app: Callable[[dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = {**scope, "path": "/mcp/"}
        await self.app(scope, receive, send)
