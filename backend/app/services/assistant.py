"""Ассистент «Иришка», обращения к оператору и уведомления."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, not_found
from app.core.events import bus
from app.db.base import utcnow
from app.domain.assistant import AssistantContext, answer
from app.domain.matching import MatchProfile, match_product
from app.integrations import ml
from app.integrations.llm import ask_llm
from app.models import (
    Application,
    AssistantConversation,
    AssistantMessage,
    Notification,
    Organization,
    SupportMessage,
    SupportTicket,
    User,
)
from app.schemas.support import (
    AnswerOut,
    ConversationOut,
    MessageOut,
    NotificationOut,
    TicketMessageOut,
    TicketOut,
)
from app.services import organizations as orgs
from app.services.catalog import list_products, product_spec

GREETING = "Здравствуйте! Я Иришка. Помогу с документами, статусом заявки и расчётом платежа."
HANDOFF = "Передал обращение оператору. Пишите сюда — ответит сотрудник банка, без ИИ."
QUICK = [
    "Какие документы нужны?",
    "Что со статусом заявки?",
    "Как уменьшить платёж?",
    "Нужна консультация оператора",
]
_PERSONAL = re.compile(r"статус|что дальше|дальше с заяв", re.IGNORECASE)
_PRODUCT = re.compile(r"документ|выписк|платеж|платёж|уменьш|продукт|ставк", re.IGNORECASE)


def _is_personal(text: str) -> bool:
    return bool(_PERSONAL.search(text)) and not _PRODUCT.search(text)


async def _conversation(session: AsyncSession, user: User, org_id: str | None) -> AssistantConversation:
    conv = (
        await session.execute(
            select(AssistantConversation)
            .where(AssistantConversation.user_id == user.id)
            .order_by(AssistantConversation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if conv is None:
        conv = AssistantConversation(user_id=user.id, organization_id=org_id)
        session.add(conv)
        await session.commit()
    return conv


def _msg(m: AssistantMessage) -> MessageOut:
    return MessageOut(id=m.id, role=m.role, text=m.text, product_card=m.product_card, at=m.at)


async def get_conversation(session: AsyncSession, user: User, org_id: str | None) -> ConversationOut:
    conv = await _conversation(session, user, org_id)
    rows = (
        await session.execute(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conv.id)
            .order_by(AssistantMessage.id)
        )
    ).scalars()
    ticket = await _open_ticket(session, user)
    return ConversationOut(
        id=conv.id,
        greeting=GREETING,
        quick_questions=QUICK,
        messages=[_msg(m) for m in rows],
        ticket_id=ticket.id if ticket else None,
    )


async def clear_conversation(session: AsyncSession, user: User) -> None:
    for conv in (
        await session.execute(select(AssistantConversation).where(AssistantConversation.user_id == user.id))
    ).scalars():
        await session.delete(conv)
    await session.commit()


def _titles(sources: Any, cited_ids: set[str]) -> list[str]:
    found: list[str] = []
    for item in sources or []:
        document = item.get("document") if isinstance(item, dict) else None
        raw = document if isinstance(document, dict) else item if isinstance(item, dict) else {}
        if not isinstance(raw, dict) or raw.get("knowledge_id") not in cited_ids:
            continue
        title = str(raw.get("title") or "").rsplit(": ", 1)[0].strip()
        if title and title not in found:
            found.append(title)
    return found


_INTERNAL_TERMS = re.compile(
    r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b|\b(?:eligibility|equipment|services|ip|ooo)\b|Признаки применимости",
    re.IGNORECASE,
)


def _safe_reply(value: Any) -> str | None:
    reply = re.sub(r"\s*\[[a-z0-9._-]+\]", "", str(value or "")).strip()
    if not reply or _INTERNAL_TERMS.search(reply):
        return None
    return reply


async def _ml_reply(question: str) -> tuple[str, str] | None:
    rag = await ml.assistant_answer({"query": question, "limit": 5})
    if rag and rag.get("answer"):
        cited_ids = set(re.findall(r"\[([a-z0-9._-]+)\]", str(rag["answer"]), re.IGNORECASE))
        reply = _safe_reply(rag["answer"])
        if not reply:
            return None
        titles = _titles(rag.get("sources"), cited_ids)
        if titles:
            reply = f"{reply}\n\nИсточники: {'; '.join(titles[:3])}"
        return reply, "ml"
    return None


async def _owned_app(session: AsyncSession, user: User, application_id: str | None) -> Application | None:
    if not application_id:
        return None
    app = await session.get(Application, application_id)
    if app is None:
        return None
    from app.core.deps import get_user_org

    await get_user_org(session, user, app.organization_id)
    return app


async def _open_ticket(session: AsyncSession, user: User) -> SupportTicket | None:
    return (
        await session.execute(
            select(SupportTicket)
            .where(SupportTicket.user_id == user.id, SupportTicket.status != "closed")
            .order_by(SupportTicket.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _context(
    session: AsyncSession, org: Organization | None, app: Application | None = None
) -> AssistantContext:
    ctx = AssistantContext()
    if org is None:
        return ctx
    if app is None:
        app = (
            await session.execute(
                select(Application)
                .where(Application.organization_id == org.id)
                .order_by(Application.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if app is not None:
        ctx.last_app_id, ctx.last_app_status = app.id, app.status
        ctx.last_app_comment = app.comment or app.manual_reason
        ctx.last_app_product = str((app.product_snapshot or {}).get("name") or "") or None
        ctx.last_app_amount = float(app.amount) if app.amount else None
        items = (app.info_request or {}).get("items") if isinstance(app.info_request, dict) else None
        titles = [str(i.get("title")) for i in items or [] if isinstance(i, dict) and i.get("title")]
        ctx.last_app_info = ", ".join(titles[:4]) or None
    profile = MatchProfile(
        goal=org.goal, amount=org.amount, months=org.months, frequency=org.frequency, collateral=org.collateral,
        age=org.age, late=org.late,
    )  # fmt: skip
    scored = [(match_product(product_spec(p), profile), p) for p in await list_products(session)]
    if scored:
        best, p = max(scored, key=lambda x: x[0].score)
        ctx.recommended_product = {
            "id": p.id,
            "name": p.name,
            "short": p.short,
            "reason": best.reasons[0] if best.reasons else "",
        }
    return ctx


async def ask(
    session: AsyncSession, user: User, text: str, org_id: str | None, application_id: str | None = None
) -> AnswerOut:
    from app.core.deps import get_user_org

    app = await _owned_app(session, user, application_id)
    org = None
    if app is not None:
        org = await get_user_org(session, user, app.organization_id)
    elif org_id:
        org = await get_user_org(session, user, org_id)
    else:
        found = await orgs.list_orgs(session, user)
        org = found[0] if found else None
    conv = await _conversation(session, user, org.id if org else None)
    question = text.strip()
    u = AssistantMessage(conversation_id=conv.id, role="user", text=question)
    session.add(u)
    ticket = await _open_ticket(session, user)
    if ticket is not None:
        session.add(
            SupportMessage(ticket_id=ticket.id, author_role="client", author_name=user.name, text=question)
        )
        if ticket.status == "answered":
            ticket.status = "open"
        await bus.publish("ticket.created", {"id": ticket.id, "company": org.name if org else ""}, bank=True)
        await session.commit()
        return AnswerOut(user=_msg(u), assistant=None, source="operator")
    ctx = await _context(session, org, app)
    reply, card = answer(question, ctx)
    source = "rules"
    if re.fullmatch(
        r"(привет|здравствуй(те)?|добрый (день|вечер|утро)|хай)[!.,\s]*", question, re.IGNORECASE
    ):
        pass
    elif _is_personal(question):
        llm = _safe_reply(await ask_llm(question, reply))
        if llm:
            reply, source = llm, "llm"
    else:
        hit = await _ml_reply(question)
        if hit:
            reply, source = hit
    a = AssistantMessage(conversation_id=conv.id, role="assistant", text=reply, product_card=card)
    session.add(a)
    await session.commit()
    return AnswerOut(user=_msg(u), assistant=_msg(a), source=source)


# ───────────────────────── обращения ─────────────────────────


async def _ticket_out(session: AsyncSession, t: SupportTicket) -> TicketOut:
    org = await session.get(Organization, t.organization_id)
    msgs = (
        await session.execute(
            select(SupportMessage).where(SupportMessage.ticket_id == t.id).order_by(SupportMessage.id)
        )
    ).scalars()
    return TicketOut(
        id=t.id, company=org.name if org else "", application_id=t.application_id, question=t.question, status=t.status,
        created_at=t.created_at, messages=[TicketMessageOut.model_validate(m, from_attributes=True) for m in msgs],
    )  # fmt: skip


async def create_ticket(
    session: AsyncSession,
    user: User,
    org: Organization,
    question: str,
    application_id: str | None,
    conversation_id: str | None = None,
) -> TicketOut:
    import secrets

    t = SupportTicket(
        id=f"TK-{secrets.randbelow(900000) + 100000}", organization_id=org.id, user_id=user.id,
        application_id=application_id, question=question.strip(),
    )  # fmt: skip
    session.add(t)
    await session.flush()
    session.add(
        SupportMessage(ticket_id=t.id, author_role="client", author_name=user.name, text=question.strip())
    )
    if conversation_id:
        session.add(AssistantMessage(conversation_id=conversation_id, role="assistant", text=HANDOFF))
    await session.commit()
    await bus.publish("ticket.created", {"id": t.id, "company": org.name}, bank=True)
    return await _ticket_out(session, t)


async def list_tickets(session: AsyncSession, user: User, bank: bool) -> list[TicketOut]:
    stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc())
    if not bank:
        stmt = stmt.where(SupportTicket.user_id == user.id)
    return [await _ticket_out(session, t) for t in (await session.execute(stmt)).scalars()]


async def _get_ticket(session: AsyncSession, ticket_id: str) -> SupportTicket:
    t = await session.get(SupportTicket, ticket_id)
    if t is None:
        raise not_found("Обращение")
    return t


async def get_ticket(session: AsyncSession, user: User, bank: bool, ticket_id: str) -> TicketOut:
    t = await _get_ticket(session, ticket_id)
    if not bank and t.user_id != user.id:
        raise not_found("Обращение")
    return await _ticket_out(session, t)


async def reply_ticket(session: AsyncSession, operator: User, ticket_id: str, text: str) -> TicketOut:
    t = await _get_ticket(session, ticket_id)
    if t.status == "closed":
        raise forbidden("Обращение закрыто")
    session.add(
        SupportMessage(ticket_id=t.id, author_role="bank", author_name=operator.name, text=text.strip())
    )
    t.status = "answered"
    conv = await _conversation(session, await session.get(User, t.user_id), t.organization_id)  # type: ignore[arg-type]
    session.add(AssistantMessage(conversation_id=conv.id, role="operator", text=text.strip(), at=utcnow()))
    session.add(
        Notification(
            user_id=t.user_id,
            type="ticket.replied",
            title="Оператор ответил на обращение",
            payload={"id": t.id},
        )
    )
    await session.commit()
    await bus.publish("ticket.replied", {"id": t.id, "text": text.strip()}, users=[t.user_id])
    return await _ticket_out(session, t)


async def set_ticket_status(session: AsyncSession, ticket_id: str, status: str) -> TicketOut:
    t = await _get_ticket(session, ticket_id)
    t.status = status
    await session.commit()
    return await _ticket_out(session, t)


# ───────────────────────── уведомления ─────────────────────────


async def list_notifications(session: AsyncSession, user: User) -> list[NotificationOut]:
    rows = (
        await session.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    ).scalars()
    return [NotificationOut.model_validate(n, from_attributes=True) for n in rows]


async def mark_read(session: AsyncSession, user: User, notification_id: str | None) -> None:
    stmt = select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if notification_id:
        stmt = stmt.where(Notification.id == notification_id)
    for n in (await session.execute(stmt)).scalars():
        n.read_at = utcnow()
    await session.commit()
