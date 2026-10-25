from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import and_, case, func, or_, select

from app.core.deps import Admin, Bank, Session
from app.core.errors import ApiError, not_found, validation
from app.core.idempotency import run_idempotent
from app.db.base import utcnow
from app.domain.finance import QuoteInput, quote_math
from app.domain.scoring import ScoringRules, safe_alt_amount
from app.models import Application, ApplicationEvent, ExternalCheck, ReviewCheck, RiskAssessment
from app.schemas.application import ApplicationOut, EventOut
from app.schemas.bank import (
    AssignBulkIn,
    AssignIn,
    AuditOut,
    AuditVerifyOut,
    BankDetailOut,
    BankListOut,
    BankRowOut,
    BankStatsOut,
    ChecklistIn,
    ChecklistItem,
    CheckRunOut,
    DecisionIn,
    DemoScenarioIn,
    ExternalCheckOut,
    NoteIn,
    RequestInfoIn,
    RequestTemplate,
    ScoringOut,
)
from app.schemas.support import TicketMessageIn, TicketOut, TicketPatch
from app.services import applications as svc
from app.services import assistant as support
from app.services import checks, seed
from app.services.catalog import get_rules, save_rules, spec_from_snapshot
from app.workers.dispatcher import start_check

router = APIRouter(prefix="/bank", tags=["bank"])


def _tpl(id_: str, kind: str, title: str) -> RequestTemplate:
    return RequestTemplate(id=id_, kind=kind, title=title, text=title)  # type: ignore[arg-type]


# Шаблоны запроса. Три разных вида: приложить документ, дополнить данные, ответить на уточняющий вопрос.
TEMPLATES = [
    _tpl("income_cert", "document", "Справка о доходах"),
    _tpl("statement", "document", "Выписка по расчётному счёту за последние 6 месяцев"),
    _tpl("loan_contracts", "document", "Действующие кредитные договоры"),
    _tpl("collateral_doc", "document", "Документ на предлагаемый залог"),
    _tpl("tax_report", "document", "Налоговая отчётность за последний период"),
    _tpl("loans_payments", "data", "Ежемесячные платежи по действующим кредитам, ₽"),
    _tpl("staff", "data", "Количество сотрудников"),
    _tpl("revenue_3m", "data", "Выручка за последние 3 месяца, ₽"),
    _tpl("source", "clarify", "За счёт каких поступлений планируете погашать платежи?"),
    _tpl("collateral", "clarify", "Опишите предлагаемый залог"),
    _tpl("purpose", "clarify", "На что именно пойдут средства?"),
]
DECIDED = ("approved", "alternative", "rejected", "signed", "funded", "withdrawn")
STATUSES = (
    "submitted",
    "checking",
    "review",
    "needs_info",
    "approved",
    "alternative",
    "rejected",
    "signed",
    "funded",
    "withdrawn",
)
# Система ещё не запускалась: заявку только приняли или проверка идёт прямо сейчас.
FRESH = ("submitted", "checking")
# Итог, который поставила система и который аналитик ещё не подтверждал.
AUTO = ("approved", "alternative", "rejected")
CLOSED = ("signed", "funded", "withdrawn")


@router.get("/me")
async def me(user: Bank) -> dict[str, Any]:
    return {"id": user.id, "name": user.name, "operator_id": user.operator_id, "role": user.role}


def _row(a: Application, extra: dict[str, Any] | None) -> BankRowOut:
    hours = int((utcnow() - a.created_at).total_seconds() // 3600)
    pack = extra or {}
    return BankRowOut(
        id=a.id, company=a.company, inn=a.inn, amount=a.amount, months=a.months, product_id=a.product_id,
        product_name=a.product_snapshot.get("name", ""), status=a.status, assignee=a.assignee,
        score=pack.get("score"), approval_pct=pack.get("approval_pct"),
        complexity=pack.get("complexity"), priority=pack.get("priority"),
        operator_decided=bool(a.manual_reason), created_at=a.created_at, hours_in_queue=max(hours, 0),
    )  # fmt: skip


async def _scores(session: Session, ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    rows = await session.execute(
        select(RiskAssessment.application_id, RiskAssessment.score, RiskAssessment.inputs)
        .where(RiskAssessment.application_id.in_(ids))
        .order_by(RiskAssessment.created_at)
    )
    out: dict[str, dict[str, Any]] = {}
    for app_id, score, inputs in rows:
        data = inputs or {}
        out[app_id] = {
            "score": score,
            "approval_pct": data.get("approval_pct"),
            "complexity": data.get("complexity"),
            "priority": data.get("priority"),
        }
    return out


async def _list(session: Session, stmt, limit: int, offset: int, sort: str) -> BankListOut:
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    if sort in ("ease", "urgency"):
        rows = list((await session.execute(stmt)).scalars())
        scores = await _scores(session, [a.id for a in rows])
        order = {"low": 0, "medium": 1, "high": 2}
        field = "complexity" if sort == "ease" else "priority"
        rows.sort(
            key=lambda a: order.get((scores.get(a.id) or {}).get(field) or "medium", 1),
            reverse=sort == "urgency",
        )
        page = rows[offset : offset + limit]
        return BankListOut(
            items=[_row(a, scores.get(a.id)) for a in page], total=total, limit=limit, offset=offset
        )
    if sort == "oldest":
        stmt = stmt.order_by(Application.created_at.asc())
    elif sort == "amount":
        stmt = stmt.order_by(Application.amount.desc())
    elif sort == "priority":
        # Сначала то, где система уже закончила и ждёт человека, внутри группы — самые старые.
        rank = case(
            (Application.status == "review", 0),
            (and_(Application.status.in_(AUTO), Application.manual_reason.is_(None)), 1),
            (Application.status == "checking", 2),
            (Application.status == "submitted", 3),
            else_=4,
        )
        stmt = stmt.order_by(rank, Application.created_at.asc())
    else:
        stmt = stmt.order_by(Application.created_at.desc())
    rows = list((await session.execute(stmt.limit(limit).offset(offset))).scalars())
    scores = await _scores(session, [a.id for a in rows])
    return BankListOut(
        items=[_row(a, scores.get(a.id)) for a in rows], total=total, limit=limit, offset=offset
    )


def _system_checked():
    """Проверка системы завершена, аналитик своё решение ещё не фиксировал."""
    return or_(
        Application.status == "review",
        and_(Application.status.in_(AUTO), Application.manual_reason.is_(None)),
    )


def _lane_clause(lane: str):
    fresh = Application.status.in_(FRESH)
    waiting = Application.status == "needs_info"
    system = _system_checked()
    if lane == "new":
        return fresh
    if lane == "system":
        return system
    if lane == "waiting":
        return waiting
    if lane == "inbox":
        return or_(fresh, system)
    return or_(
        Application.status.in_(CLOSED),
        and_(Application.status.in_(AUTO), Application.manual_reason.is_not(None)),
    )


@router.get("/applications", response_model=BankListOut)
async def queue(
    user: Bank,
    session: Session,
    status: str | None = None,
    lane: Annotated[str | None, Query(pattern="^(inbox|new|system|waiting|done)$")] = None,
    owner: Annotated[str, Query(pattern="^(all|mine|free)$")] = "all",
    product_id: str | None = None,
    period: Annotated[str, Query(pattern="^(all|1|7|30)$")] = "all",
    q: str | None = None,
    sort: Annotated[str, Query(pattern="^(oldest|newest|amount|priority|ease|urgency)$")] = "newest",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Application)
    if lane:
        stmt = stmt.where(_lane_clause(lane))
    if status:
        stmt = stmt.where(Application.status == status)
    if owner == "mine":
        stmt = stmt.where(Application.assignee == user.operator_id)
    elif owner == "free":
        stmt = stmt.where(Application.assignee.is_(None))
    if product_id:
        stmt = stmt.where(Application.product_id == product_id)
    if period != "all":
        stmt = stmt.where(Application.created_at >= utcnow() - timedelta(days=int(period)))
    if q and q.strip():
        variants = {
            q.strip(),
            q.strip().lower(),
            q.strip().upper(),
            q.strip().capitalize(),
            q.strip().title(),
        }
        clauses = []
        for v in variants:
            clauses += [
                Application.company.contains(v),
                Application.inn.contains(v),
                Application.id.contains(v),
            ]
        stmt = stmt.where(or_(*clauses))
    return await _list(session, stmt, limit, offset, sort)


@router.get("/applications/stats", response_model=BankStatsOut)
async def stats(_: Bank, session: Session):
    reviewed = Application.manual_reason.is_not(None)
    rows = (
        await session.execute(
            select(Application.status, reviewed, func.count()).group_by(Application.status, reviewed)
        )
    ).all()
    counts: dict[str, int] = {}
    fresh = system = waiting = done = 0
    for status, is_reviewed, n in rows:
        counts[status] = counts.get(status, 0) + n
        if status in FRESH:
            fresh += n
        elif status == "needs_info":
            waiting += n
        elif status == "review" or (status in AUTO and not is_reviewed):
            system += n
        elif status in CLOSED or (status in AUTO and is_reviewed):
            done += n
    return BankStatsOut(
        all=sum(counts.values()),
        inbox=fresh + system,
        fresh=fresh,
        system=system,
        waiting=waiting,
        done=done,
        **{s: counts.get(s, 0) for s in STATUSES},
    )


@router.post("/applications/assign-bulk")
async def assign_bulk(body: AssignBulkIn, user: Bank, session: Session) -> dict[str, Any]:
    done, skipped = [], []
    for app_id in body.application_ids:
        try:
            await svc.assign(session, user, await svc.get_app(session, app_id, lock=True))
            done.append(app_id)
        except ApiError:
            await session.rollback()
            skipped.append(app_id)
    return {"assigned": done, "skipped": skipped}


@router.get("/applications/{app_id}", response_model=BankDetailOut)
async def detail(app_id: str, user: Bank, session: Session):
    app = await svc.get_app(session, app_id)
    out = await svc.build_out(session, app, user.role)
    external = (
        await session.execute(
            select(ExternalCheck).where(ExternalCheck.application_id == app_id).order_by(ExternalCheck.at)
        )
    ).scalars()
    latest: dict[str, ExternalCheck] = {e.source: e for e in external}
    marks = {
        c.key: c
        for c in (
            await session.execute(select(ReviewCheck).where(ReviewCheck.application_id == app_id))
        ).scalars()
    }
    checklist = [
        ChecklistItem(
            key=k,
            checked=bool(marks[k].checked) if k in marks else False,
            by=marks[k].by if k in marks else None,
        )
        for k in ("numbers", "debt", "collateral")
    ]
    summary = (
        f"Автосводка. {app.company} (ИНН {app.inn}) просит {svc.rub(app.amount)} на {app.months} мес. "
        f"по продукту «{app.product_snapshot.get('name', '')}». Выручка {svc.rub(app.revenue)}, расходы {svc.rub(app.expenses)}, "
        f"платежи по долгам {svc.rub(app.debt)}."
    )
    if out.risk:
        summary += f" Скоринг {out.risk.score}/100, нагрузка {round(out.risk.load * 100)}%."
    return BankDetailOut(
        application=out,
        external_checks=[ExternalCheckOut(source=e.source, status=e.status, payload=e.payload, at=e.at) for e in latest.values()],
        checklist=checklist, note=app.internal_note or "", summary=summary, history=await svc.list_events(session, app_id),
    )  # fmt: skip


@router.get("/applications/{app_id}/events", response_model=list[EventOut])
async def app_events(app_id: str, _: Bank, session: Session):
    await svc.get_app(session, app_id)
    return await svc.list_events(session, app_id)


@router.post("/applications/{app_id}/assign", response_model=ApplicationOut)
async def assign(app_id: str, user: Bank, session: Session, body: AssignIn | None = None):
    app = await svc.get_app(session, app_id, lock=True)
    await svc.assign(session, user, app)
    return await svc.build_out(session, app, user.role)


@router.post("/applications/{app_id}/check", status_code=202)
async def run_check(app_id: str, user: Bank, session: Session) -> dict[str, Any]:
    app = await svc.get_app(session, app_id, lock=True)
    run_id = await start_check(session, app, user)
    return {"check_id": run_id, "status": "checking"}


@router.get("/applications/{app_id}/check", response_model=CheckRunOut)
async def check_progress(app_id: str, _: Bank, session: Session):
    run = await checks.latest_run(session, app_id)
    if run is None:
        raise not_found("Проверка")
    return checks.run_out(run)


@router.get("/applications/{app_id}/external-checks", response_model=list[ExternalCheckOut])
async def external_checks(app_id: str, _: Bank, session: Session):
    rows = (
        await session.execute(
            select(ExternalCheck).where(ExternalCheck.application_id == app_id).order_by(ExternalCheck.at)
        )
    ).scalars()
    return [ExternalCheckOut(source=e.source, status=e.status, payload=e.payload, at=e.at) for e in rows]


@router.get("/applications/{app_id}/scoring", response_model=ScoringOut)
async def scoring(app_id: str, _: Bank, session: Session):
    r = (
        await session.execute(
            select(RiskAssessment)
            .where(RiskAssessment.application_id == app_id)
            .order_by(RiskAssessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if r is None:
        raise not_found("Скоринг")
    return ScoringOut(
        score=r.score, load=r.load, cash=r.cash, pay=r.pay, result=r.result, alt=r.alt, factors=r.explanation,
        reasons=list((r.inputs or {}).get("reasons", [])), rules_version=r.rules_version, created_at=r.created_at,
    )  # fmt: skip


@router.post("/applications/{app_id}/request-info", response_model=ApplicationOut)
async def request_info(app_id: str, body: RequestInfoIn, user: Bank, session: Session):
    items = [i.model_dump() for i in body.items if i.title.strip()]
    if not items and not (body.text or "").strip():
        raise validation("Выберите, что нужно от клиента: документы, данные или уточнение", "items")
    app = await svc.get_app(session, app_id, lock=True)
    await svc.request_info(session, user, app, body.text, body.version, items=items, message=body.message)
    return await svc.build_out(session, app, user.role)


@router.post("/applications/{app_id}/decision", response_model=ApplicationOut)
async def decision(app_id: str, body: DecisionIn, request: Request, user: Bank, session: Session):
    async def handler() -> ApplicationOut:
        app = await svc.get_app(session, app_id, lock=True)
        spec = spec_from_snapshot(app.product_snapshot)
        peak = quote_math(
            spec, QuoteInput(app.amount, app.months, app.days, app.rate, app.scheme, app.fee)
        ).peak
        rules = await get_rules(session)
        alt = safe_alt_amount(spec, rules, app.revenue - app.expenses, app.debt, peak, app.amount)
        await svc.manual_decision(
            session, user, app, body.decision, body.reason, body.offer_amount, body.version, alt
        )
        return await svc.build_out(session, app, user.role)

    return await run_idempotent(request, session, user, handler, required=False)


@router.put("/applications/{app_id}/checklist", response_model=list[ChecklistItem])
async def checklist(app_id: str, body: ChecklistIn, user: Bank, session: Session):
    await svc.get_app(session, app_id)
    row = await session.get(ReviewCheck, (app_id, body.key))
    if row is None:
        row = ReviewCheck(application_id=app_id, key=body.key)
        session.add(row)
    row.checked, row.by, row.at = body.checked, user.operator_id, utcnow()
    await svc.add_event(
        session,
        app_id,
        "checklist",
        f"Чек-лист «{body.key}»: {'отмечено' if body.checked else 'снято'}",
        actor=user,
    )
    await session.commit()
    rows = {
        c.key: c
        for c in (
            await session.execute(select(ReviewCheck).where(ReviewCheck.application_id == app_id))
        ).scalars()
    }
    return [
        ChecklistItem(
            key=k, checked=bool(rows[k].checked) if k in rows else False, by=rows[k].by if k in rows else None
        )
        for k in ("numbers", "debt", "collateral")
    ]


@router.put("/applications/{app_id}/note")
async def note(app_id: str, body: NoteIn, _: Bank, session: Session) -> dict[str, str]:
    app = await svc.get_app(session, app_id)
    app.internal_note = body.text
    await session.commit()
    return {"text": body.text}


@router.get("/request-templates", response_model=list[RequestTemplate])
async def request_templates(_: Bank):
    return TEMPLATES


@router.get("/decisions", response_model=BankListOut)
async def decisions(
    _: Bank,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await _list(
        session, select(Application).where(Application.status.in_(DECIDED)), limit, offset, "newest"
    )


# ── поддержка ──


@router.get("/support/tickets", response_model=list[TicketOut])
async def tickets(
    user: Bank,
    session: Session,
    status: Annotated[str | None, Query(pattern="^(open|answered|closed)$")] = None,
):
    rows = await support.list_tickets(session, user, bank=True)
    return [t for t in rows if status is None or t.status == status]


@router.get("/support/tickets/{ticket_id}", response_model=TicketOut)
async def ticket(ticket_id: str, user: Bank, session: Session):
    return await support.get_ticket(session, user, True, ticket_id)


@router.post("/support/tickets/{ticket_id}/reply", response_model=TicketOut)
async def reply(ticket_id: str, body: TicketMessageIn, user: Bank, session: Session):
    return await support.reply_ticket(session, user, ticket_id, body.text)


@router.patch("/support/tickets/{ticket_id}", response_model=TicketOut)
async def patch_ticket(ticket_id: str, body: TicketPatch, _: Bank, session: Session):
    return await support.set_ticket_status(session, ticket_id, body.status)


# ── администрирование и демо ──


@router.get("/scoring/rules", response_model=ScoringRules)
async def get_scoring_rules(_: Bank, session: Session):
    return await get_rules(session)


@router.put("/scoring/rules", response_model=ScoringRules)
async def put_scoring_rules(body: ScoringRules, _: Admin, session: Session):
    return await save_rules(session, body)


@router.post("/demo/scenarios", response_model=BankRowOut, status_code=201)
async def demo_scenario(body: DemoScenarioIn, _: Bank, session: Session):
    app = await seed.create_scenario(session, body.kind)
    await svc.publish_update(app)
    return _row(app, None)


@router.get("/audit", response_model=AuditOut)
async def audit(
    _: Admin,
    session: Session,
    application_id: str | None = None,
    type: str | None = None,  # noqa: A002
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(ApplicationEvent)
    if application_id:
        stmt = stmt.where(ApplicationEvent.application_id == application_id)
    if type:
        stmt = stmt.where(ApplicationEvent.type == type)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(stmt.order_by(ApplicationEvent.id.desc()).limit(limit).offset(offset))
    ).scalars()
    items = [
        {"id": e.id, "application_id": e.application_id, "type": e.type, "text": e.text, "actor_role": e.actor_role,
         "at": e.at.isoformat(), "hash": e.hash}
        for e in rows
    ]  # fmt: skip
    return AuditOut(items=items, total=total)


@router.get("/audit/verify", response_model=AuditVerifyOut)
async def audit_verify(_: Admin, session: Session, application_id: str | None = None):
    ok, checked, broken = await svc.verify_chain(session, application_id)
    return AuditVerifyOut(ok=ok, checked=checked, broken_at=broken)
