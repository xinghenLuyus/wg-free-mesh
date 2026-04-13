from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.responses import ApiResponse, ok
from app.domain.models import now_utc
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
def system_status() -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.system_status())


@ws_router.websocket("/events")
async def events(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        async for event in realtime_service.subscribe():
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
