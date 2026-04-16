from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.v1.deps import require_current_user
from app.core.config import settings
from app.core.responses import ApiResponse, ok
from app.domain.models import now_utc
from app.services.auth_service import auth_service
from app.services.control_plane_service import control_plane_service
from app.services.realtime_service import realtime_service

router = APIRouter(prefix="/system", tags=["system"])
ws_router = APIRouter(prefix="/ws", tags=["ws"])


@router.get("/health")
def health() -> ApiResponse[dict[str, object]]:
    return ok(
        {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "timestamp": now_utc().isoformat(),
        }
    )


@router.get("/status")
def system_status(_: Annotated[object, Depends(require_current_user)]) -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.system_status())


@ws_router.websocket("/events")
async def events(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    try:
        auth_service.require_user(token)
    except Exception:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    subscription = realtime_service.open_subscription()
    loop = asyncio.get_running_loop()
    next_tick = loop.time() + 1.0
    try:
        await websocket.send_json(realtime_service.make_event("system.clock.tick", {"timestamp": now_utc().isoformat()}))
        await websocket.send_json(realtime_service.make_event("system.status.snapshot", control_plane_service.system_status()))
        while True:
            timeout = max(0.0, next_tick - loop.time())
            try:
                event = await asyncio.wait_for(subscription.get(), timeout=timeout)
            except asyncio.TimeoutError:
                await websocket.send_json(realtime_service.make_event("system.clock.tick", {"timestamp": now_utc().isoformat()}))
                next_tick = loop.time() + 1.0
                continue
            await websocket.send_json(event)
            while loop.time() >= next_tick:
                await websocket.send_json(realtime_service.make_event("system.clock.tick", {"timestamp": now_utc().isoformat()}))
                next_tick += 1.0
    except WebSocketDisconnect:
        return
    finally:
        realtime_service.close_subscription(subscription)
