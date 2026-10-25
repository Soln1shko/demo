"""Постановка проверок в очередь: ARQ (Redis) в проде, фоновая asyncio-задача без Redis."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import session_factory
from app.models import Application, User
from app.services import checks

_tasks: set[asyncio.Task[None]] = set()
_arq_pool: Any = None


async def _run_local(application_id: str, run_id: str) -> None:
    async with session_factory()() as session:
        await checks.run_check(session, application_id, run_id)


async def start_check(session: AsyncSession, app: Application, operator: User | None) -> str:
    """Переводит заявку в «checking» и запускает фоновую проверку. Возвращает id прогона."""
    run = await checks.begin_check(session, operator, app)
    settings = get_settings()
    if settings.redis_url:
        global _arq_pool
        from arq import create_pool
        from arq.connections import RedisSettings

        if _arq_pool is None:
            _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await _arq_pool.enqueue_job("run_check_job", app.id, run.id)
    else:
        task = asyncio.create_task(_run_local(app.id, run.id))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return run.id


async def wait_for_background() -> None:
    """Для тестов: дождаться завершения локальных задач."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
