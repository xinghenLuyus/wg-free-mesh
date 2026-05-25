from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class PublicSourceGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if settings.dev_test_api_enabled or not settings.public_origin_host:
            return await call_next(request)
        if request.url.path.startswith("/api/internal/"):
            return await call_next(request)

        host = self._request_host(request)
        if host != settings.public_origin_host:
            return self._reject("PUBLIC_HOST_REJECTED", "Public host is not allowed")

        origin = request.headers.get("origin", "").strip().rstrip("/")
        if origin and origin not in settings.allowed_origins:
            return self._reject("PUBLIC_ORIGIN_REJECTED", "Public origin is not allowed")
        return await call_next(request)

    @staticmethod
    def _request_host(request: Request) -> str:
        host = request.headers.get("host", "").strip()
        if "://" in host:
            host = urlparse(host).netloc
        return host.lower()

    @staticmethod
    def _reject(code: str, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": code, "message": message, "detail": {}}},
        )
