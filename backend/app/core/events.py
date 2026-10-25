"""Шина событий для SSE. Память процесса + (опционально) Redis pub/sub между процессами."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.core.config import get_settings

log = structlog.get_logger()
CHANNEL = "alfa:events"


@dataclass(eq=False)
class Subscriber:
    user_id: str
    is_bank: bool
    org_ids: set[str]
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(maxsize=200))

    def wants(self, audience: dict[str, Any]) -> bool:
        if self.user_id in audience.get("users", []):
            return True
        if audience.get("bank") and self.is_bank:
            return True
        return bool(self.org_ids & set(audience.get("orgs", [])))


class EventBus:
    def __init__(self) -> None:
        self._subs: set[Subscriber] = set()
        self._recent: deque[dict[str, Any]] = deque(maxlen=300)
        self._seq = 0
        self._redis: Any = None
        self._listener: asyncio.Task[None] | None = None

    async def start(self) -> None:
        url = get_settings().redis_url
        if url and self._redis is None:
            from redis import asyncio as aioredis

            self._redis = aioredis.from_url(url, decode_responses=True)
            self._listener = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listener:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._listener
        if self._redis:
            await self._redis.aclose()
        self._redis = self._listener = None

    async def publish(
        self,
        event: str,
        data: dict[str, Any],
        *,
        users: list[str] | None = None,
        orgs: list[str] | None = None,
        bank: bool = False,
    ) -> None:
        message = {
            "event": event,
            "data": data,
            "audience": {"users": users or [], "orgs": orgs or [], "bank": bank},
        }
        redis = self._redis or await self._publisher()
        if redis is not None:
            try:
                await redis.publish(CHANNEL, json.dumps(message))
                return
            except Exception:  # noqa: BLE001 — деградируем до локальной доставки
                log.warning("redis_publish_failed")
        self._deliver(message)

    async def _publisher(self) -> Any:
        """В воркере шина не запущена: создаём подключение лениво."""
        url = get_settings().redis_url
        if not url:
            return None
        from redis import asyncio as aioredis

        self._redis = aioredis.from_url(url, decode_responses=True)
        return self._redis

    def _deliver(self, message: dict[str, Any]) -> None:
        self._seq += 1
        message = {**message, "id": f"{int(time.time() * 1000)}-{self._seq}"}
        self._recent.append(message)
        for sub in list(self._subs):
            if sub.wants(message["audience"]):
                with contextlib.suppress(asyncio.QueueFull):
                    sub.queue.put_nowait(message)

    async def _listen(self) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        async for raw in pubsub.listen():
            if raw.get("type") == "message":
                with contextlib.suppress(Exception):
                    self._deliver(json.loads(raw["data"]))

    def subscribe(self, sub: Subscriber, last_event_id: str | None = None) -> list[dict[str, Any]]:
        """Регистрирует подписчика и возвращает пропущенные события (Last-Event-ID)."""
        missed: list[dict[str, Any]] = []
        if last_event_id:
            seen = False
            for m in self._recent:
                if seen and sub.wants(m["audience"]):
                    missed.append(m)
                if m["id"] == last_event_id:
                    seen = True
        self._subs.add(sub)
        return missed

    def unsubscribe(self, sub: Subscriber) -> None:
        self._subs.discard(sub)


bus = EventBus()
