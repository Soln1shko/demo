"""Ограничение частоты запросов (скользящее окно). Redis, если настроен, иначе память процесса."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import ApiError

_hits: dict[str, deque[float]] = defaultdict(deque)
_redis = None


def reset_rate_limits() -> None:
    _hits.clear()


class RateLimit:
    def __init__(self, times: int, seconds: int) -> None:
        self.times, self.seconds = times, seconds

    async def __call__(self, request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        ip = request.client.host if request.client else "unknown"
        key = f"rl:{request.url.path}:{ip}"
        if settings.redis_url:
            if await self._redis_hit(settings.redis_url, key):
                return
            raise self._error()
        now = time.monotonic()
        q = _hits[key]
        while q and now - q[0] > self.seconds:
            q.popleft()
        if len(q) >= self.times:
            raise self._error()
        q.append(now)

    async def _redis_hit(self, url: str, key: str) -> bool:
        global _redis
        try:
            if _redis is None:
                from redis import asyncio as aioredis

                _redis = aioredis.from_url(url)
            count = await _redis.incr(key)
            if count == 1:
                await _redis.expire(key, self.seconds)
            return count <= self.times
        except Exception:  # noqa: BLE001 — при сбое Redis не блокируем пользователей
            return True

    def _error(self) -> ApiError:
        return ApiError(429, "rate_limited", "Слишком много запросов. Попробуйте позже.")
