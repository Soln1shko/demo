"""JSON-кэш: Redis в проде, память процесса если Redis недоступен."""

from __future__ import annotations

import json
import time
from typing import Any

from app.core.config import get_settings

_memory: dict[str, tuple[float, str]] = {}
_redis = None


async def _client():
    global _redis
    url = get_settings().redis_url
    if not url:
        return None
    if _redis is None:
        from redis import asyncio as aioredis

        _redis = aioredis.from_url(url)
    return _redis


async def get_json(key: str) -> Any | None:
    try:
        redis = await _client()
        if redis is not None:
            raw = await redis.get(key)
            return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001 — кабинет работает и без Redis
        pass
    packed = _memory.get(key)
    if packed is None or packed[0] < time.monotonic():
        _memory.pop(key, None)
        return None
    return json.loads(packed[1])


async def set_json(key: str, value: Any, ttl: int) -> None:
    raw = json.dumps(value, ensure_ascii=False)
    try:
        redis = await _client()
        if redis is not None:
            await redis.set(key, raw, ex=ttl)
            return
    except Exception:  # noqa: BLE001
        pass
    _memory[key] = (time.monotonic() + ttl, raw)
