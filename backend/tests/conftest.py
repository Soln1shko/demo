import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

_tmp = tempfile.mkdtemp(prefix="alfa-tests-")
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{Path(_tmp, 'test.db').as_posix()}",
        "STORAGE_DIR": str(Path(_tmp, "files")),
        "PASSWORD_HASH_FAST": "true",
        "CHECK_STEP_DELAY": "0",
        "RATE_LIMIT_ENABLED": "false",
        "SEED_ON_START": "false",
        "REDIS_URL": "",
    }
)

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.events import bus  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import dispose_engine, get_engine, session_factory  # noqa: E402
from app.integrations.storage import reset_storage  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.seed import seed_all  # noqa: E402


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    get_settings.cache_clear()
    reset_storage()
    await dispose_engine()
    import app.models  # noqa: F401

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with session_factory()() as session:
        await seed_all(session)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await dispose_engine()
    bus._subs.clear()  # noqa: SLF001


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
