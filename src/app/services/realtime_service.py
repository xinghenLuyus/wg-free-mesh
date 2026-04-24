from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.domain.models import now_utc

RealtimeEventPayload = dict[str, object]
SubscriptionItem = RealtimeEventPayload | None
SUBSCRIPTION_QUEUE_SIZE = 256


class RealtimeSubscription:
    def __init__(self, maxsize: int = SUBSCRIPTION_QUEUE_SIZE) -> None:
        self._queue: asyncio.Queue[SubscriptionItem] = asyncio.Queue(maxsize=maxsize)
        self._closed = False
        self._overflowed = False

    async def get(self) -> SubscriptionItem:
        return await self._queue.get()

    def put_nowait(self, item: SubscriptionItem) -> None:
        if self._closed:
            return
        self._queue.put_nowait(item)

    def close(self) -> None:
        self._closed = True

    def mark_overflowed(self) -> None:
        self._overflowed = True
        self._closed = True

    @property
    def overflowed(self) -> bool:
        return self._overflowed

    @property
    def closed(self) -> bool:
        return self._closed

    def empty(self) -> bool:
        return self._queue.empty()


class RealtimeService:
    def __init__(self) -> None:
        self._subscribers: set[RealtimeSubscription] = set()
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
        for subscription in subscribers:
            subscription.close()
            try:
                subscription.put_nowait(None)
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
        stale: list[RealtimeSubscription] = []
        for subscription in self._subscribers:
            try:
                subscription.put_nowait(event)
            except asyncio.QueueFull:
                subscription.mark_overflowed()
                stale.append(subscription)
        for subscription in stale:
            self._subscribers.discard(subscription)

    def open_subscription(self) -> RealtimeSubscription:
        subscription = RealtimeSubscription()
        if self._shutting_down:
            subscription.close()
            subscription.put_nowait(None)
            return subscription
        self._subscribers.add(subscription)
        return subscription

    def close_subscription(self, subscription: RealtimeSubscription) -> None:
        subscription.close()
        self._subscribers.discard(subscription)

    async def subscribe(self) -> AsyncIterator[RealtimeEventPayload]:
        subscription = self.open_subscription()
        try:
            while True:
                item = await subscription.get()
                if item is None:
                    break
                yield item
        finally:
            self.close_subscription(subscription)


realtime_service = RealtimeService()
