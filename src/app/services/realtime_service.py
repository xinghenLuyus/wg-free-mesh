from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.domain.models import now_utc


class RealtimeService:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, object]]] = set()

    async def publish(self, event_type: str, payload: dict[str, object]) -> None:
        event = {
            "type": event_type,
            "timestamp": now_utc().isoformat(),
            "payload": payload,
        }
        stale: list[asyncio.Queue[dict[str, object]]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)

    async def subscribe(self) -> AsyncIterator[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)


realtime_service = RealtimeService()
