"""Воркер ARQ: `arq app.workers.arq_worker.WorkerSettings`."""

from typing import Any

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, session_factory
from app.services import checks


async def run_check_job(ctx: dict[str, Any], application_id: str, run_id: str) -> None:
    async with session_factory()() as session:
        await checks.run_check(session, application_id, run_id)


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()


async def shutdown(ctx: dict[str, Any]) -> None:
    await dispose_engine()


class WorkerSettings:
    functions = [run_check_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url or "redis://localhost:6379")
    max_jobs = 10
    job_timeout = 120
