"""Персонализированная новостная лента."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.feed_rules import PROFILE_LABELS, FeedContext, _explain, dynamic_items, select_feed
from app.models import Application, FeedDismissal, FeedItem, FinanceMonth, Organization
from app.schemas.support import FeedExplainOut, FeedItemIn, FeedItemOut, FeedOut


async def _context(session: AsyncSession, org: Organization) -> FeedContext:
    statuses: dict[str, list[str]] = defaultdict(list)
    rows = await session.execute(
        select(Application.id, Application.status)
        .where(Application.organization_id == org.id)
        .order_by(Application.created_at.desc())
    )
    for app_id, status in rows:
        statuses[status].append(app_id)
    has_history = (
        await session.execute(
            select(FinanceMonth.month)
            .where(FinanceMonth.organization_id == org.id, FinanceMonth.source != "Анкета")
            .limit(1)
        )
    ).first() is not None
    return FeedContext(
        profile=org.profile, goal=org.goal, age=org.age, revenue=org.revenue, expenses=org.expenses, debt=org.debt,
        has_history=has_history, app_statuses=dict(statuses),
    )  # fmt: skip


def to_dict(i: FeedItem) -> dict:
    return {
        "id": i.id, "kind": i.kind, "title": i.title, "body": i.body, "icon": i.icon, "cta": i.cta,
        "conditions": i.conditions, "priority": i.priority, "active": i.active,
    }  # fmt: skip


async def editorial(session: AsyncSession) -> list[dict]:
    return [to_dict(i) for i in (await session.execute(select(FeedItem))).scalars()]


async def _dismissed(session: AsyncSession, org_id: str) -> set[str]:
    return set(
        (
            await session.execute(
                select(FeedDismissal.item_id).where(FeedDismissal.organization_id == org_id)
            )
        ).scalars()
    )


async def next_step(session: AsyncSession, org: Organization) -> dict:
    """Одна персональная рекомендация для обзора: срочные действия по заявкам, затем общий совет."""
    ctx = await _context(session, org)
    urgent = dynamic_items(ctx)
    if urgent:
        top = max(urgent, key=lambda i: i["priority"])
        return {"title": top["title"], "body": top["body"], "cta": top["cta"]}
    if not ctx.has_history:
        return {
            "title": "Добавьте помесячные показатели",
            "body": "С историей за несколько месяцев обзор и подбор продуктов станут точнее.",
            "cta": {"label": "Добавить месяц", "route": "/app/overview"},
        }
    return {
        "title": "Подберите продукт под задачу",
        "body": "Сравните платёж и запас денег до подачи заявки.",
        "cta": {"label": "Открыть финансирование", "route": "/app/products"},
    }


async def get_feed(
    session: AsyncSession, org: Organization, limit: int = 10, profile: str | None = None
) -> FeedOut:
    ctx = await _context(session, org)
    if profile:
        ctx.profile = profile
    items = select_feed(await editorial(session), ctx, await _dismissed(session, org.id), limit)
    return FeedOut(
        profile=ctx.profile,
        items=[
            FeedItemOut(**{k: i.get(k, {} if k == "cta" else "") for k in FeedItemOut.model_fields})
            for i in items
        ],
    )


async def explain(session: AsyncSession, org: Organization) -> FeedExplainOut:
    ctx = await _context(session, org)
    active = [
        f"{i['title']} — " + "; ".join(r)
        for i in await editorial(session)
        if i["active"] and (r := _explain(i["conditions"] or {}, ctx)) is not None
    ]
    return FeedExplainOut(
        profile=org.profile, profile_label=PROFILE_LABELS.get(org.profile, org.profile), goal=org.goal,
        applications=ctx.app_count, active_rules=active,
    )  # fmt: skip


async def dismiss(session: AsyncSession, org: Organization, item_id: str) -> None:
    if await session.get(FeedDismissal, (org.id, item_id)) is None:
        session.add(FeedDismissal(organization_id=org.id, item_id=item_id))
        await session.commit()


async def restore_all(session: AsyncSession, org: Organization) -> None:
    for row in (
        await session.execute(select(FeedDismissal).where(FeedDismissal.organization_id == org.id))
    ).scalars():
        await session.delete(row)
    await session.commit()


async def upsert_item(session: AsyncSession, body: FeedItemIn) -> FeedItem:
    row = await session.get(FeedItem, body.id)
    data = body.model_dump()
    if row is None:
        row = FeedItem(**data)
        session.add(row)
    else:
        for k, v in data.items():
            setattr(row, k, v)
    await session.commit()
    return row
