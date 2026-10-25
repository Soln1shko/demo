import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Header, Request
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings
from app.core.deps import CurrentUser, Session
from app.core.errors import ApiError
from app.core.events import Subscriber, bus
from app.integrations import mocks
from app.models.user import BANK_ROLES
from app.schemas.support import NotificationOut
from app.services import assistant as support
from app.services import organizations as orgs
from app.services.catalog import get_rules

router = APIRouter(tags=["system"])


# ── SSE и уведомления ──


@router.get("/events/stream")
async def stream(
    request: Request,
    user: CurrentUser,
    session: Session,
    last_event_id: Annotated[str | None, Header()] = None,
):
    sub = Subscriber(
        user_id=user.id,
        is_bank=user.role in BANK_ROLES,
        org_ids={o.id for o in await orgs.list_orgs(session, user)},
    )
    missed = bus.subscribe(sub, last_event_id)
    await session.close()

    async def gen() -> AsyncIterator[dict[str, str]]:
        try:
            yield {"event": "ready", "data": json.dumps({"user": user.id})}
            for m in missed:
                yield {"event": m["event"], "data": json.dumps(m["data"]), "id": m["id"]}
            while True:
                m = await sub.queue.get()
                yield {"event": m["event"], "data": json.dumps(m["data"]), "id": m["id"]}
        finally:
            bus.unsubscribe(sub)

    return EventSourceResponse(
        gen(), ping=15, headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )


@router.get("/notifications", response_model=list[NotificationOut])
async def notifications(user: CurrentUser, session: Session, unread: bool = False):
    rows = await support.list_notifications(session, user)
    return [n for n in rows if not unread or n.read_at is None]


@router.post("/notifications/read-all", status_code=204)
async def read_all(user: CurrentUser, session: Session):
    await support.mark_read(session, user, None)


@router.post("/notifications/{notification_id}/read", status_code=204)
async def read_one(notification_id: str, user: CurrentUser, session: Session):
    await support.mark_read(session, user, notification_id)


# ── служебные ──


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(session: Session) -> dict[str, Any]:
    checks: dict[str, str] = {}
    try:
        await session.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc.__class__.__name__}"
    settings = get_settings()
    if settings.redis_url:
        try:
            from redis import asyncio as aioredis

            client = aioredis.from_url(settings.redis_url)
            await client.ping()
            await client.aclose()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {exc.__class__.__name__}"
    ok = all(v == "ok" for v in checks.values())
    if not ok:
        raise ApiError(
            503, "not_ready", "Сервис не готов: " + ", ".join(f"{k}={v}" for k, v in checks.items())
        )
    return {"status": "ok", "checks": checks}


@router.get("/version")
async def version(session: Session) -> dict[str, Any]:
    settings = get_settings()
    rules = await get_rules(session)
    return {
        "version": "1.0.0",
        "commit": settings.commit_sha,
        "env": settings.app_env,
        "rules_version": rules.version,
    }


# ── симуляторы внешних систем (внутренний контур) ──


async def _internal(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    token = get_settings().internal_token
    if not token or x_internal_token != token:
        raise ApiError(404, "not_found", "Объект не найден")


internal = APIRouter(prefix="/internal/mock", tags=["internal"], include_in_schema=True)


@internal.get("/fns/company/{inn}")
async def mock_fns(inn: str, x_internal_token: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    await _internal(x_internal_token)
    return await mocks.fns.company(inn)


@internal.get("/bki/report/{inn}")
async def mock_bki(inn: str, x_internal_token: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    await _internal(x_internal_token)
    return await mocks.bki.report(inn)


@internal.post("/esign/sign")
async def mock_esign(
    payload: dict[str, str], x_internal_token: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    await _internal(x_internal_token)
    return await mocks.esign.sign(payload.get("application_id", ""), payload.get("signer", ""))


@internal.post("/payout/disburse")
async def mock_payout(
    payload: dict[str, Any], x_internal_token: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    await _internal(x_internal_token)
    return await mocks.payout.disburse(
        str(payload.get("application_id", "")), float(payload.get("amount", 0))
    )
