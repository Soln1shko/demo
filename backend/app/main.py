from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.events import bus
from app.core.logging import configure_logging, install_middlewares
from app.db.base import Base
from app.db.session import dispose_engine, get_engine, session_factory
from app.services.seed import seed_all

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging()
    if settings.create_tables_on_start:
        import app.models  # noqa: F401  регистрация таблиц

        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if settings.seed_on_start:
        async with session_factory()() as session:
            await seed_all(session)
    await bus.start()
    log.info("started", env=settings.app_env, commit=settings.commit_sha)
    try:
        yield
    finally:
        await bus.stop()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Альфа Пульс — умный кредитный кабинет",
        version="1.0.0",
        description="Клиентский кабинет и банковская обработка кредитной заявки малого бизнеса. Данные синтетические.",
        lifespan=lifespan,
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    install_middlewares(app)
    install_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    except ImportError:  # pragma: no cover
        pass
    return app


app = create_app()
