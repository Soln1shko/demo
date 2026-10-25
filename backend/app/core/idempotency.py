"""Идемпотентность мутаций по заголовку Idempotency-Key (хранится в БД)."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models import IdempotencyKey, User


async def run_idempotent(
    request: Request,
    session: AsyncSession,
    user: User,
    handler: Callable[[], Awaitable[Any]],
    *,
    required: bool = True,
) -> Any:
    key = request.headers.get("Idempotency-Key")
    if not key:
        if required:
            raise ApiError(400, "idempotency_key_required", "Передайте заголовок Idempotency-Key")
        return await handler()
    if len(key) > 80:
        raise ApiError(400, "idempotency_key_invalid", "Idempotency-Key слишком длинный")
    body = await request.body()
    fingerprint = hashlib.sha256(f"{request.method}{request.url.path}".encode() + body).hexdigest()
    existing = await session.get(IdempotencyKey, (key, user.id))
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise ApiError(
                422, "idempotency_key_reused", "Этот Idempotency-Key уже использован с другим запросом"
            )
        return JSONResponse(existing.response, status_code=existing.status_code)
    result = await handler()
    payload = jsonable_encoder(result)
    session.add(
        IdempotencyKey(key=key, user_id=user.id, request_hash=fingerprint, status_code=200, response=payload)
    )
    await session.commit()
    return payload
