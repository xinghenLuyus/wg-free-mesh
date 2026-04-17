from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.domain.models import now_utc


class RealtimeService:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, object]]] = set()
        self._event_id = 0

    def make_event(self, event_type: str, payload: dict[str, object]) -> dict[str, object]:
        self._event_id += 1
        return {
            "id": str(self._event_id),
            "type": event_type,
            "timestamp": now_utc().isoformat(),
            "payload": payload,
        }

    async def publish(self, event_type: str, payload: dict[str, object]) -> None:
        event = self.make_event(event_type, payload)
        stale: list[asyncio.Queue[dict[str, object]]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)

    def open_subscription(self) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def close_subscription(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        self._subscribers.discard(queue)

    async def subscribe(self) -> AsyncIterator[dict[str, object]]:
        queue = self.open_subscription()
        try:
            while True:
                yield await queue.get()
        finally:
            self.close_subscription(queue)


realtime_service = RealtimeService()
