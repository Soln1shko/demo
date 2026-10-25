from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.v1.common import CurrentOrg
from app.core.deps import Client, CurrentUser, Session, get_user_org
from app.core.errors import ApiError, not_found
from app.core.idempotency import run_idempotent
from app.domain.finance import QuoteInput, quote_math
from app.domain.state_machine import ACTIVE_STATUSES
from app.models import Application, Document
from app.models.user import BANK_ROLES
from app.schemas.application import (
    ApplicationOut,
    ContractOut,
    DocumentOut,
    EventOut,
    ExportOut,
    RiskOut,
    SignIn,
    SubmitIn,
    SupplementIn,
    VersionIn,
)
from app.schemas.product import ScheduleOut, ScheduleRowOut
from app.services import applications as svc
from app.services import drafts
from app.services.catalog import spec_from_snapshot
from app.workers.dispatcher import start_check

router = APIRouter(prefix="/applications", tags=["applications"])
DONE = {"funded", "rejected", "withdrawn"}


async def _mutate(
    request: Request,
    session: Session,
    user: Client,
    build: Callable[[], Awaitable[Application]],
    *,
    required: bool = True,
) -> Any:
    async def handler() -> Any:
        app = await build()
        return await svc.build_out(session, app, user.role)

    return await run_idempotent(request, session, user, handler, required=required)


@router.post("", response_model=ApplicationOut, status_code=201)
async def submit(body: SubmitIn, request: Request, session: Session, user: Client):
    org = await get_user_org(session, user, body.organization_id)

    async def build() -> Application:
        return await drafts.submit(session, user, org, body.consent, body.document_ids)

    result = await _mutate(request, session, user, build)
    if isinstance(result, JSONResponse):
        return result
    return JSONResponse(result, status_code=201)


@router.get("", response_model=list[ApplicationOut])
async def list_applications(
    org: CurrentOrg,
    session: Session,
    user: Client,
    filter: Annotated[str, Query(pattern="^(all|active|done)$")] = "all",  # noqa: A002
    status: str | None = None,
):
    stmt = (
        select(Application)
        .where(Application.organization_id == org.id)
        .order_by(Application.created_at.desc())
    )
    rows = list((await session.execute(stmt)).scalars())
    if status:
        rows = [a for a in rows if a.status == status]
    elif filter == "active":
        rows = [a for a in rows if a.status in ACTIVE_STATUSES]
    elif filter == "done":
        rows = [a for a in rows if a.status in DONE]
    return await svc.build_many(session, rows, user.role)


async def _own(session: Session, user: Client, app_id: str) -> Application:
    return await svc.get_client_app(session, user, app_id)


@router.get("/{app_id}", response_model=ApplicationOut)
async def get_application(app_id: str, session: Session, user: Client):
    return await svc.build_out(session, await _own(session, user, app_id), user.role)


@router.get("/{app_id}/events", response_model=list[EventOut])
async def events(app_id: str, session: Session, user: Client):
    await _own(session, user, app_id)
    return await svc.list_events(session, app_id)


@router.get("/{app_id}/decision", response_model=RiskOut)
async def decision(app_id: str, session: Session, user: Client):
    out = await svc.build_out(session, await _own(session, user, app_id), user.role)
    if out.risk is None:
        raise not_found("Результат проверки")
    return out.risk


@router.get("/{app_id}/schedule", response_model=ScheduleOut)
async def schedule(app_id: str, session: Session, user: Client):
    app = await _own(session, user, app_id)
    spec = spec_from_snapshot(app.product_snapshot)
    res = quote_math(spec, QuoteInput(app.amount, app.months, app.days, app.rate, app.scheme, app.fee))
    return ScheduleOut(
        unit="day" if spec.kind == "overdraft" else "month", interest=res.interest,
        rows=[ScheduleRowOut(n=r.n, payment=r.payment, principal=r.principal, interest=r.interest, balance=r.balance) for r in res.rows],
    )  # fmt: skip


@router.get("/{app_id}/contract", response_model=ContractOut)
async def contract(app_id: str, session: Session, user: Client):
    app = await _own(session, user, app_id)
    if app.status not in ("approved", "signed", "funded"):
        raise ApiError(409, "invalid_transition", "Условия для подписания доступны после одобрения")
    spec = spec_from_snapshot(app.product_snapshot)
    res = quote_math(spec, QuoteInput(app.amount, app.months, app.days, app.rate, app.scheme, app.fee))
    return ContractOut(
        company=app.company, product_name=app.product_snapshot["name"], amount=app.amount, rate=app.rate,
        scheme=app.scheme, daily=spec.daily is not None, days=app.days, months=app.months, total=res.total,
        cost=res.cost, peak=res.peak, first=res.first, fee=app.fee,
        note="Демонстрационный договор. Подпись смоделирована и юридической силы не имеет.",
    )  # fmt: skip


@router.get("/{app_id}/export", response_model=ExportOut)
async def export(app_id: str, session: Session, user: Client):
    app = await _own(session, user, app_id)
    out = await svc.build_out(session, app, user.role)
    events_ = await svc.list_events(session, app_id)
    return ExportOut(
        application=out.model_dump(mode="json"), events=[e.model_dump(mode="json") for e in events_]
    )


@router.get("/{app_id}/documents", response_model=list[DocumentOut])
async def documents(app_id: str, session: Session, user: CurrentUser):
    if user.role in BANK_ROLES:
        await svc.get_app(session, app_id)
    else:
        await svc.get_client_app(session, user, app_id)
    rows = (
        await session.execute(
            select(Document).where(Document.application_id == app_id).order_by(Document.created_at)
        )
    ).scalars()
    return list(rows)


@router.post("/{app_id}/check", status_code=202)
async def start_check_client(app_id: str, session: Session, user: Client) -> dict[str, Any]:
    """Запуск автоматической проверки клиентом (как в демо: кнопка «Проверить заявку»).

    Проверка полностью автоматическая (ФНС → БКИ → скоринг); ручное решение остаётся за банком.
    """
    app = await svc.get_client_app(session, user, app_id, lock=True)
    if app.status != "submitted":
        raise ApiError(409, "invalid_transition", "Проверку можно запустить для новой заявки")
    run_id = await start_check(session, app, None)
    return {"check_id": run_id, "status": "checking"}


@router.post("/{app_id}/supplement", response_model=ApplicationOut)
async def supplement(app_id: str, body: SupplementIn, request: Request, session: Session, user: Client):
    async def build() -> Application:
        app = await svc.get_client_app(session, user, app_id, lock=True)
        return await svc.supplement(session, user, app, body.document_ids, body.version, body.answers)

    return await _mutate(request, session, user, build, required=False)


@router.post("/{app_id}/accept-offer", response_model=ApplicationOut)
async def accept_offer(app_id: str, body: VersionIn, request: Request, session: Session, user: Client):
    async def build() -> Application:
        app = await svc.get_client_app(session, user, app_id, lock=True)
        return await svc.accept_offer(session, user, app, body.version)

    return await _mutate(request, session, user, build, required=False)


@router.post("/{app_id}/sign", response_model=ApplicationOut)
async def sign(app_id: str, body: SignIn, request: Request, session: Session, user: Client):
    async def build() -> Application:
        app = await svc.get_client_app(session, user, app_id, lock=True)
        return await svc.sign(session, user, app, body.agreed, body.version)

    return await _mutate(request, session, user, build)


@router.post("/{app_id}/fund", response_model=ApplicationOut)
async def fund(app_id: str, body: VersionIn, request: Request, session: Session, user: Client):
    async def build() -> Application:
        app = await svc.get_client_app(session, user, app_id, lock=True)
        return await svc.fund(session, user, app, body.version)

    return await _mutate(request, session, user, build)


@router.post("/{app_id}/withdraw", response_model=ApplicationOut)
async def withdraw(app_id: str, body: VersionIn, request: Request, session: Session, user: Client):
    async def build() -> Application:
        app = await svc.get_client_app(session, user, app_id, lock=True)
        return await svc.withdraw(session, user, app, body.version)

    return await _mutate(request, session, user, build)
