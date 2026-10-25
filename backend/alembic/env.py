import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

config = context.config
target_metadata = Base.metadata


def _do_run(connection) -> None:  # noqa: ANN001
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        await conn.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(_run_online())
