"""Заявки: сборка представлений, события с хеш-цепочкой, переходы состояний."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, conflict, not_found
from app.core.events import bus
from app.db.base import utcnow
from app.domain import state_machine as sm
from app.domain.assistant import STATUS_LABELS
from app.domain.finance import QuoteInput, quote_math
from app.models import (
    Application,
    ApplicationEvent,
    Document,
    Notification,
    OrganizationMember,
    RiskAssessment,
    User,
)
from app.models.user import BANK_ROLES
from app.schemas.application import (
    ApplicationOut,
    CalcOut,
    DocumentOut,
    EventOut,
    FactorOut,
    InfoRequestOut,
    RiskOut,
)
from app.schemas.product import ProductOut
from app.services.catalog import spec_from_snapshot


def rub(n: float) -> str:
    return f"{round(n):,}".replace(",", "\u00a0") + "\u00a0₽"


def new_app_id() -> str:
    return "AK-" + uuid4().hex[:8].upper()


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


# ───────────────────────── события и аудит ─────────────────────────


def _event_hash(prev: str, type_: str, text: str, at: datetime, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(f"{prev}|{type_}|{text}|{at.isoformat()}|{body}".encode()).hexdigest()


async def add_event(
    session: AsyncSession,
    application_id: str,
    type_: str,
    text: str,
    *,
    actor: User | None = None,
    role: str | None = None,
    payload: dict[str, Any] | None = None,
) -> ApplicationEvent:
    prev = (
        await session.execute(
            select(ApplicationEvent.hash)
            .where(ApplicationEvent.application_id == application_id)
            .order_by(ApplicationEvent.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none() or ""
    at = utcnow()
    payload = payload or {}
    event = ApplicationEvent(
        application_id=application_id,
        actor_id=actor.id if actor else None,
        actor_role=role or (actor.role if actor else "system"),
        type=type_,
        text=text,
        payload=payload,
        prev_hash=prev,
        hash=_event_hash(prev, type_, text, at, payload),
        at=at,
    )
    session.add(event)
    await session.flush()
    return event


async def verify_chain(
    session: AsyncSession, application_id: str | None = None
) -> tuple[bool, int, int | None]:
    stmt = select(ApplicationEvent).order_by(ApplicationEvent.application_id, ApplicationEvent.id)
    if application_id:
        stmt = stmt.where(ApplicationEvent.application_id == application_id)
    prev_by_app: dict[str, str] = defaultdict(str)
    checked = 0
    for e in (await session.execute(stmt)).scalars():
        expected = _event_hash(prev_by_app[e.application_id], e.type, e.text, e.at, e.payload or {})
        if e.prev_hash != prev_by_app[e.application_id] or e.hash != expected:
            return False, checked, e.id
        prev_by_app[e.application_id] = e.hash
        checked += 1
    return True, checked, None


# ───────────────────────── представление ─────────────────────────


def calc_for(app: Application) -> CalcOut:
    spec = spec_from_snapshot(app.product_snapshot)
    result = quote_math(spec, QuoteInput(app.amount, app.months, app.days, app.rate, app.scheme, app.fee))
    cash = app.revenue - app.expenses
    return CalcOut(
        interest=result.interest, cost=result.cost, total=result.total, first=result.first,
        last=result.last, peak=result.peak, monthly=result.monthly,
        rest_at_peak=cash - app.debt - result.peak,
    )  # fmt: skip


def risk_out(r: RiskAssessment) -> RiskOut:
    extra = r.inputs or {}
    return RiskOut(
        score=r.score, load=r.load, cash=r.cash, pay=r.pay, result=r.result, alt=r.alt,
        factors=[FactorOut(**f) for f in r.explanation or []], reasons=_reasons(r),
        rules_version=r.rules_version, created_at=r.created_at,
        approval_pct=extra.get("approval_pct"), risk_band=extra.get("risk_band"),
        complexity=extra.get("complexity"), priority=extra.get("priority"),
    )  # fmt: skip


def _reasons(r: RiskAssessment) -> list[str]:
    return list((r.inputs or {}).get("reasons", []))


async def build_many(
    session: AsyncSession, apps: list[Application], viewer_role: str
) -> list[ApplicationOut]:
    if not apps:
        return []
    ids = [a.id for a in apps]
    docs: dict[str, list[Document]] = defaultdict(list)
    for d in (
        await session.execute(
            select(Document).where(Document.application_id.in_(ids)).order_by(Document.created_at)
        )
    ).scalars():
        docs[d.application_id or ""].append(d)
    risks: dict[str, RiskAssessment] = {}
    for r in (
        await session.execute(
            select(RiskAssessment)
            .where(RiskAssessment.application_id.in_(ids))
            .order_by(RiskAssessment.created_at)
        )
    ).scalars():
        risks[r.application_id] = r  # последняя перезаписывает предыдущие
    role_kind = "bank" if viewer_role in BANK_ROLES else "client"
    result = []
    for a in apps:
        result.append(
            ApplicationOut(
                id=a.id,
                organization_id=a.organization_id,
                status=a.status,
                version=a.version,
                product=ProductOut(**a.product_snapshot),
                amount=a.amount,
                months=a.months,
                days=a.days,
                rate=a.rate,
                scheme=a.scheme,
                fee=a.fee,
                goal=a.goal,
                company=a.company,
                inn=a.inn,
                legal=a.legal,
                region=a.region,
                revenue=a.revenue,
                expenses=a.expenses,
                debt=a.debt,
                age=a.age,
                late=a.late,
                consent=a.consent,
                assignee=a.assignee,
                offer_amount=a.offer_amount,
                original_amount=a.original_amount,
                comment=a.comment,
                manual_reason=a.manual_reason,
                requested_doc_count=a.requested_doc_count,
                info_request=InfoRequestOut(**a.info_request) if a.info_request else None,
                created_at=a.created_at,
                updated_at=a.updated_at,
                risk=risk_out(risks[a.id]) if a.id in risks else None,
                calc=calc_for(a),
                documents=[DocumentOut.model_validate(d) for d in docs.get(a.id, [])],
                next_actions=sm.next_actions(a.status, role_kind),
            )  # fmt: skip
        )
    return result


async def build_out(session: AsyncSession, app: Application, viewer_role: str) -> ApplicationOut:
    return (await build_many(session, [app], viewer_role))[0]


async def list_events(session: AsyncSession, application_id: str) -> list[EventOut]:
    rows = await session.execute(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application_id)
        .order_by(ApplicationEvent.id)
    )
    return [EventOut.model_validate(e) for e in rows.scalars()]


# ───────────────────────── доступ ─────────────────────────


async def get_app(session: AsyncSession, app_id: str, *, lock: bool = False) -> Application:
    stmt = select(Application).where(Application.id == app_id)
    if lock:
        stmt = stmt.with_for_update()
    app = (await session.execute(stmt)).scalar_one_or_none()
    if app is None:
        raise not_found("Заявка")
    return app


async def get_client_app(
    session: AsyncSession, user: User, app_id: str, *, lock: bool = False
) -> Application:
    app = await get_app(session, app_id, lock=lock)
    member = (
        await session.execute(
            select(OrganizationMember.id).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == app.organization_id,
            )
        )
    ).first()
    if member is None:
        raise not_found("Заявка")
    return app


# ───────────────────────── переходы и уведомления ─────────────────────────


def transition(
    app: Application, action: str, *, target: str | None = None, expected: int | None = None
) -> None:
    if expected is not None and expected != app.version:
        raise conflict("stale_version", "Заявка изменилась. Обновите страницу и повторите действие.")
    try:
        app.status = str(sm.apply(app.status, action, target))
    except sm.InvalidTransition as exc:
        raise ApiError(409, "invalid_transition", str(exc)) from exc
    app.version += 1
    app.updated_at = utcnow()


async def notify_org(
    session: AsyncSession, org_id: str, type_: str, title: str, payload: dict[str, Any] | None = None
) -> None:
    members = (
        await session.execute(
            select(OrganizationMember.user_id).where(OrganizationMember.organization_id == org_id)
        )
    ).scalars()
    for uid in members:
        session.add(Notification(user_id=uid, type=type_, title=title, payload=payload or {}))


async def publish_update(app: Application) -> None:
    data = {"id": app.id, "status": app.status, "version": app.version}
    await bus.publish("application.updated", data, orgs=[app.organization_id], bank=True)
    await bus.publish("queue.updated", {"id": app.id}, bank=True)


# ───────────────────────── действия клиента ─────────────────────────


async def count_docs(session: AsyncSession, app_id: str) -> int:
    return len((await session.execute(select(Document.id).where(Document.application_id == app_id))).all())


ANSWER_MAX = 1000


def _check_request_complete(app: Application, answers: dict[str, str], attached: set[str]) -> dict[str, str]:
    """Каждый пункт запроса должен быть закрыт: документ — файлом, данные и уточнение — текстом."""
    assert app.info_request
    clean: dict[str, str] = {}
    errors: list[dict[str, str]] = []
    for item in app.info_request["items"]:
        if item["kind"] == "document":
            if item["id"] not in attached:
                errors.append({"field": item["id"], "message": "Приложите документ"})
            continue
        text = (answers.get(item["id"]) or "").strip()
        if not text:
            errors.append({"field": item["id"], "message": "Заполните поле"})
        elif len(text) > ANSWER_MAX:
            errors.append({"field": item["id"], "message": f"Не больше {ANSWER_MAX} символов"})
        else:
            clean[item["id"]] = text
    if errors:
        raise ApiError(
            422, "validation_failed", "Закройте все пункты запроса банка: у каждого должен быть документ или ответ",
            errors=errors,
        )  # fmt: skip
    return clean


async def supplement(
    session: AsyncSession,
    user: User,
    app: Application,
    document_ids: list[str],
    version: int | None,
    answers: dict[str, str] | None = None,
) -> Application:
    if app.status != "needs_info":
        raise ApiError(409, "invalid_transition", "Дополнение доступно только по запросу банка")
    if document_ids:
        docs = (
            await session.execute(
                select(Document).where(
                    Document.id.in_(document_ids),
                    Document.organization_id == app.organization_id,
                    Document.application_id.is_(None),
                )
            )
        ).scalars()
        for d in docs:
            d.application_id = app.id
        await session.flush()
    summary = "Клиент добавил документы. Заявка возвращена на проверку"
    if app.info_request:
        attached = {
            d.request_item
            for d in (
                await session.execute(
                    select(Document).where(
                        Document.application_id == app.id, Document.request_item.is_not(None)
                    )
                )
            ).scalars()
        }
        clean = _check_request_complete(app, answers or {}, {i for i in attached if i})
        docs_n = sum(1 for i in app.info_request["items"] if i["kind"] == "document")
        summary = f"Клиент ответил на запрос банка: документов — {docs_n}, ответов — {len(clean)}. Заявка возвращена на проверку"
        app.info_request = {**app.info_request, "answers": clean}
    elif await count_docs(session, app.id) <= (
        app.requested_doc_count if app.requested_doc_count is not None else 1
    ):
        raise ApiError(
            422, "validation_failed", "Добавьте запрошенный документ к исходному комплекту",
            errors=[{"field": "documents", "message": "Нужен новый документ"}],
        )  # fmt: skip
    transition(app, "supplement", expected=version)
    await add_event(session, app.id, "supplemented", summary, actor=user, role="client")
    await session.commit()
    await bus.publish("application.supplemented", {"id": app.id}, bank=True)
    await publish_update(app)
    return app


async def accept_offer(
    session: AsyncSession, user: User, app: Application, version: int | None
) -> Application:
    if app.status != "alternative":
        raise ApiError(409, "invalid_transition", "Нет альтернативного предложения для принятия")
    transition(app, "accept_offer", expected=version)
    app.original_amount = app.amount
    app.amount = app.offer_amount or app.amount
    await add_event(
        session, app.id, "offer_accepted", f"Клиент принял альтернативную сумму {rub(app.amount)}",
        actor=user, role="client", payload={"original": app.original_amount, "amount": app.amount},
    )  # fmt: skip
    await session.commit()
    await publish_update(app)
    return app


async def sign(
    session: AsyncSession, user: User, app: Application, agreed: bool, version: int | None
) -> Application:
    from app.integrations.mocks import esign

    if not agreed:
        raise ApiError(422, "validation_failed", "Сначала подтвердите ознакомление с условиями")
    transition(app, "sign", expected=version)
    sig = await esign.sign(app.id, user.email)
    await add_event(
        session, app.id, "signed", "Клиент подтвердил условия. Договор подписан (демо)",
        actor=user, role="client", payload=sig,
    )  # fmt: skip
    await session.commit()
    await publish_update(app)
    return app


async def fund(session: AsyncSession, user: User, app: Application, version: int | None) -> Application:
    from app.integrations.mocks import payout

    transition(app, "fund", expected=version)
    res = await payout.disburse(app.id, app.amount)
    await add_event(
        session, app.id, "funded", "Выдача на расчетный счет", actor=user, role="client", payload=res
    )
    await notify_org(
        session, app.organization_id, "application.funded", f"Заявка {app.id}: кредит выдан", {"id": app.id}
    )
    await session.commit()
    await publish_update(app)
    return app


async def withdraw(session: AsyncSession, user: User, app: Application, version: int | None) -> Application:
    transition(app, "withdraw", expected=version)
    await add_event(session, app.id, "withdrawn", "Заявка отозвана клиентом", actor=user, role="client")
    await session.commit()
    await publish_update(app)
    return app


# ───────────────────────── действия банка ─────────────────────────


async def assign(session: AsyncSession, operator: User, app: Application) -> Application:
    if app.status not in ("submitted", "review"):
        raise ApiError(
            409, "invalid_transition", "Взять в работу можно новую заявку или заявку на рассмотрении"
        )
    already = app.assignee == operator.operator_id and app.status == "review"
    app.assignee = operator.operator_id
    if not already:
        transition(app, "assign")
        await add_event(
            session, app.id, "assigned", f"Заявка назначена аналитику {operator.operator_id}",
            actor=operator, payload={"assignee": operator.operator_id},
        )  # fmt: skip
    await session.commit()
    await publish_update(app)
    return app


KIND_LABEL = {"document": "документы", "data": "данные", "clarify": "уточнения"}


def _request_summary(items: list[dict[str, Any]]) -> str:
    parts = []
    for kind in ("document", "data", "clarify"):
        titles = [i["title"] for i in items if i["kind"] == kind]
        if titles:
            parts.append(f"{KIND_LABEL[kind]}: {'; '.join(titles)}")
    return ". ".join(parts)


async def request_info(
    session: AsyncSession,
    operator: User,
    app: Application,
    text: str | None,
    version: int | None,
    *,
    items: list[dict[str, Any]] | None = None,
    message: str | None = None,
) -> Application:
    """Запрос банка. Новый формат — `items` (несколько пунктов сразу); `text` — старый, один комментарий."""
    transition(app, "request_info", expected=version)
    app.requested_doc_count = await count_docs(session, app.id)
    if items:
        prepared: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for it in items:
            title = it["title"].strip()
            key = (it["kind"], title.lower())
            if not title or key in seen:
                continue
            seen.add(key)
            prepared.append({
                "id": uuid4().hex[:8], "kind": it["kind"], "title": title, "template_id": it.get("template_id"),
            })  # fmt: skip
        note = (message or "").strip() or None
        app.info_request = {
            "requested_at": utcnow().isoformat(),
            "message": note,
            "items": prepared,
            "answers": {},
        }
        summary = _request_summary(prepared)
        app.comment = note or summary
        event_text = f"Банк запросил — {summary}" + (f". Сообщение: {note}" if note else "")
    else:
        app.info_request = None
        app.comment = (text or "").strip()
        event_text = f"Банк запросил уточнение: {app.comment}"
    await add_event(session, app.id, "info_requested", event_text, actor=operator)
    await notify_org(
        session,
        app.organization_id,
        "application.needs_info",
        f"Заявка {app.id}: нужны сведения",
        {"id": app.id},
    )
    await session.commit()
    await publish_update(app)
    return app


async def manual_decision(
    session: AsyncSession,
    operator: User,
    app: Application,
    decision: str,
    reason: str,
    offer_amount: float | None,
    version: int | None,
    safe_alt: float,
) -> Application:
    revised = app.status in ("approved", "alternative", "rejected")
    if app.status != "review" and not revised:
        raise ApiError(
            409,
            "invalid_transition",
            "Решение принимается по заявке «на рассмотрении». Сначала возьмите её в работу.",
        )
    spec = spec_from_snapshot(app.product_snapshot)
    offer = None
    if decision == "alternative":
        offer = offer_amount or safe_alt
        if offer < spec.min_amount:
            raise ApiError(
                422, "validation_failed", "Посильная сумма ниже минимума продукта. Выберите отказ или одобрение.",
                errors=[{"field": "offer_amount", "message": "Сумма ниже минимума продукта"}],
            )  # fmt: skip
        offer = min(offer, spec.max_amount)
    transition(app, "decide", target=decision, expected=version)
    app.manual_reason = reason.strip()
    if offer is not None:
        app.offer_amount = offer
    elif revised:
        app.offer_amount = None  # прежнее предложение больше не действует
    title = "Решение пересмотрено аналитиком" if revised else "Ручное решение"
    await add_event(
        session, app.id, "manual_decision", f"{title}: {status_label(decision)}. {app.manual_reason}",
        actor=operator, payload={"decision": decision, "offer_amount": offer, "revised": revised},
    )  # fmt: skip
    await notify_org(
        session, app.organization_id, "application.decided",
        f"Заявка {app.id}: {status_label(decision).lower()}", {"id": app.id},
    )  # fmt: skip
    await session.commit()
    await publish_update(app)
    return app
