from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.api.v1.deps import CurrentUserDep, require_current_user
from app.core.config import settings
from app.core.responses import ApiResponse, ok
from app.domain.models import now_utc
from app.services.control_plane_service import control_plane_service
from app.services.realtime_service import realtime_service

router = APIRouter(prefix="/system", tags=["system"])
events_router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger("uvicorn.error")
SSE_CLOCK_SYNC_INTERVAL_SECONDS = 15.0


def _sse_frame(event: dict[str, object]) -> str:
    event_type = str(event.get("type", "message"))
    event_id = str(event.get("id", ""))
    data = json.dumps(jsonable_encoder(event), ensure_ascii=False, separators=(",", ":"))
    parts = [f"event: {event_type}"]
    if event_id:
        parts.append(f"id: {event_id}")
    parts.append(f"data: {data}")
    return "\n".join(parts) + "\n\n"


@router.get("/health")
def health() -> ApiResponse[dict[str, object]]:
    return ok(
        {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "timestamp": now_utc().isoformat(),
            "timezone": settings.timezone,
            "dev_test_api_enabled": settings.dev_test_api_enabled,
        }
    )


@router.get("/timezone")
def system_timezone() -> ApiResponse[dict[str, str]]:
    return ok({"timezone": settings.timezone})


@router.get("/status")
def system_status(_: Annotated[object, Depends(require_current_user)]) -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.system_status())


@events_router.get("/stream")
async def stream_events(request: Request, user: CurrentUserDep) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        subscription = realtime_service.open_subscription()
        loop = asyncio.get_running_loop()
        next_clock = loop.time() + SSE_CLOCK_SYNC_INTERVAL_SECONDS
        try:
            yield _sse_frame(realtime_service.make_event("system.status.updated", control_plane_service.system_status()))
            yield _sse_frame(
                realtime_service.make_event("system.clock.sync", {"timestamp": now_utc().isoformat(), "timezone": settings.timezone})
            )
            while True:
                if realtime_service.shutting_down:
                    break
                if await request.is_disconnected():
                    break
                if subscription.closed and subscription.empty():
                    break
                timeout = max(0.0, next_clock - loop.time())
                try:
                    event = await asyncio.wait_for(subscription.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    if subscription.closed and subscription.empty():
                        break
                    yield _sse_frame(
                        realtime_service.make_event(
                            "system.clock.sync",
                            {"timestamp": now_utc().isoformat(), "timezone": settings.timezone},
                        )
                    )
                    next_clock = loop.time() + SSE_CLOCK_SYNC_INTERVAL_SECONDS
                    continue
                if event is None:
                    break
                yield _sse_frame(event)
                if subscription.closed and subscription.empty():
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("events.stream failed for user=%s", user.username)
            raise
        finally:
            realtime_service.close_subscription(subscription)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
