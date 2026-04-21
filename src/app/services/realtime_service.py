from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.domain.models import now_utc

RealtimeEventPayload = dict[str, object]
SubscriptionItem = RealtimeEventPayload | None


class RealtimeService:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[SubscriptionItem]] = set()
        self._event_id = 0
        self._shutting_down = False

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down

    def startup(self) -> None:
        self._shutting_down = False

    async def shutdown(self) -> None:
        self._shutting_down = True
        subscribers = list(self._subscribers)
        self._subscribers.clear()
        for queue in subscribers:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

    def make_event(self, event_type: str, payload: dict[str, object]) -> RealtimeEventPayload:
        self._event_id += 1
        return {
            "id": str(self._event_id),
            "type": event_type,
            "timestamp": now_utc().isoformat(),
            "payload": payload,
        }

    async def publish(self, event_type: str, payload: dict[str, object]) -> None:
        if self._shutting_down:
            return
        event = self.make_event(event_type, payload)
        stale: list[asyncio.Queue[SubscriptionItem]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)

    def open_subscription(self) -> asyncio.Queue[SubscriptionItem]:
        queue: asyncio.Queue[SubscriptionItem] = asyncio.Queue(maxsize=100)
        if self._shutting_down:
            queue.put_nowait(None)
            return queue
        self._subscribers.add(queue)
        return queue

    def close_subscription(self, queue: asyncio.Queue[SubscriptionItem]) -> None:
        self._subscribers.discard(queue)

    async def subscribe(self) -> AsyncIterator[RealtimeEventPayload]:
        queue = self.open_subscription()
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            self.close_subscription(queue)


realtime_service = RealtimeService()
