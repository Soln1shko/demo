"""Организации, онбординг, помесячные показатели и аналитика."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, conflict, validation
from app.db.base import utcnow
from app.integrations.storage import get_storage
from app.models import (
    Application,
    AssistantConversation,
    Document,
    FinanceMonth,
    Notification,
    OnboardingDraft,
    Organization,
    OrganizationMember,
    User,
)
from app.schemas.organization import OnboardingData
from app.services.applications import rub

INN_RE = re.compile(r"^\d{10}(\d{2})?$")
ONBOARDING_FIELDS = (
    "legal", "name", "inn", "region", "age", "profile", "goal", "amount", "months", "frequency", "urgency",
    "collateral", "revenue", "expenses", "debt", "seasonality", "late",
)  # fmt: skip


def month_key(d: date | None = None) -> str:
    d = d or date.today()
    return f"{d.year}-{d.month:02d}"


# ───────────────────────── организации ─────────────────────────


async def list_orgs(session: AsyncSession, user: User) -> list[Organization]:
    stmt = (
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.created_at)
    )
    return list((await session.execute(stmt)).scalars())


async def create_org(session: AsyncSession, user: User, data: dict[str, Any]) -> Organization:
    existing = await list_orgs(session, user)
    if any(o.inn == data["inn"] for o in existing):
        raise conflict("duplicate_inn", "Компания с таким ИНН уже есть в вашем кабинете.")
    legal = data.get("legal") or ("ip" if len(data["inn"]) == 12 else "ooo")
    org = Organization(**{**data, "legal": legal})
    session.add(org)
    await session.flush()
    session.add(OrganizationMember(user_id=user.id, organization_id=org.id, role="owner"))
    session.add(
        FinanceMonth(
            organization_id=org.id,
            month=month_key(),
            revenue=org.revenue,
            expenses=org.expenses,
            debt=org.debt,
            source="Анкета",
        )  # fmt: skip
    )
    await session.commit()
    return org


async def reset_demo(session: AsyncSession, user: User) -> None:
    """Сброс кабинета: удаляются организации аккаунта со всеми данными. Аккаунт остаётся."""
    org_ids = [o.id for o in await list_orgs(session, user)]
    if org_ids:
        keys = (
            await session.execute(
                select(Document.storage_key).where(
                    Document.organization_id.in_(org_ids), Document.storage_key.is_not(None)
                )
            )
        ).scalars()
        for key in list(keys):
            if key is not None:
                await get_storage().delete(key)
        # каскады БД удалят заявки, документы, события, черновики и обращения
        await session.execute(delete(Organization).where(Organization.id.in_(org_ids)))
    await session.execute(delete(OnboardingDraft).where(OnboardingDraft.user_id == user.id))
    await session.execute(delete(AssistantConversation).where(AssistantConversation.user_id == user.id))
    await session.execute(delete(Notification).where(Notification.user_id == user.id))
    await session.commit()


# ───────────────────────── онбординг ─────────────────────────


async def get_onboarding(session: AsyncSession, user: User) -> OnboardingDraft:
    row = await session.get(OnboardingDraft, user.id)
    if row is None:
        row = OnboardingDraft(user_id=user.id, step=0, data={})
        session.add(row)
        await session.commit()
    return row


async def save_onboarding(session: AsyncSession, user: User, body: OnboardingData) -> OnboardingDraft:
    row = await get_onboarding(session, user)
    changes = body.model_dump(exclude_unset=True)
    step = changes.pop("step", None)
    data = dict(row.data)
    data.update(changes)
    row.data = data
    if step is not None:
        row.step = step
    row.updated_at = utcnow()
    await session.commit()
    return row


def validate_onboarding(o: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    def bad(field: str, msg: str) -> None:
        errors.append({"field": field, "message": msg})

    inn = str(o.get("inn") or "").strip()
    pattern = re.compile(r"^\d{12}$" if o.get("legal") == "ip" else r"^\d{10}$")
    if not str(o.get("name") or "").strip() or not str(o.get("region") or "").strip():
        bad("name", "Укажите название компании и город.")
    elif not pattern.match(inn):
        bad("inn", "Проверьте ИНН: 10 цифр для юрлица, 12 для ИП.")
    elif o.get("age") is None or o["age"] < 0:
        bad("age", "Укажите срок работы бизнеса, для нового — 0.")
    amount, months = o.get("amount"), o.get("months")
    if (
        not o.get("goal")
        or amount is None or not 50_000 <= amount <= 150_000_000
        or months is None or int(months) != months or not 1 <= months <= 120
    ):  # fmt: skip
        bad("goal", "Выберите цель, сумму от 50 тыс. до 150 млн ₽ и срок от 1 до 120 месяцев.")
    if any(o.get(k) is None or o[k] < 0 for k in ("revenue", "expenses", "debt")):
        bad("revenue", "Заполните все финансовые показатели. Если платежей нет, укажите 0.")
    return errors


async def complete_onboarding(session: AsyncSession, user: User) -> Organization:
    row = await get_onboarding(session, user)
    o = {**{"legal": "ooo", "profile": "retail", "frequency": "once", "urgency": "month", "collateral": "no",
            "seasonality": "stable", "late": False}, **row.data}  # fmt: skip
    errors = validate_onboarding(o)
    if errors:
        raise ApiError(422, "validation_failed", errors[0]["message"], errors=errors)
    org = await create_org(
        session, user,
        {
            "name": o["name"].strip(), "inn": o["inn"].strip(), "legal": o["legal"], "profile": o["profile"],
            "region": o["region"].strip(), "age": int(o["age"]), "revenue": o["revenue"], "expenses": o["expenses"],
            "debt": o["debt"], "goal": o["goal"], "amount": o["amount"], "months": int(o["months"]),
            "frequency": o["frequency"], "urgency": o["urgency"], "collateral": o["collateral"],
            "seasonality": o["seasonality"], "late": bool(o["late"]),
        },
    )  # fmt: skip
    await session.delete(row)
    await session.commit()
    return org


# ───────────────────────── помесячные показатели ─────────────────────────


async def finance_rows(session: AsyncSession, org_id: str) -> list[FinanceMonth]:
    stmt = select(FinanceMonth).where(FinanceMonth.organization_id == org_id).order_by(FinanceMonth.month)
    return list((await session.execute(stmt)).scalars())


async def upsert_month(
    session: AsyncSession, org: Organization, month: str, revenue: float, expenses: float, debt: float
):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise validation("Месяц должен быть в формате ГГГГ-ММ", "month")
    if month > month_key():
        raise validation("Нельзя добавить показатели за будущий месяц", "month")
    row = await session.get(FinanceMonth, (org.id, month))
    if row is None:
        row = FinanceMonth(organization_id=org.id, month=month, revenue=revenue, expenses=expenses, debt=debt)
        session.add(row)
    row.revenue, row.expenses, row.debt, row.source = revenue, expenses, debt, "Месячный отчет"
    await session.commit()
    return row


# ───────────────────────── аналитика ─────────────────────────

GROUPS = [
    ("На рассмотрении", ("submitted", "review", "checking")),
    ("Нужны сведения", ("needs_info",)),
    ("Есть предложение", ("approved", "alternative")),
    ("Оформлены", ("signed", "funded")),
    ("Закрыты", ("withdrawn", "rejected")),
]


def _window(n: int) -> list[str]:
    today = date.today()
    y, m = today.year, today.month
    out = []
    for i in range(n):
        mm = m - (n - 1 - i)
        yy = y + (mm - 1) // 12
        out.append(f"{yy}-{((mm - 1) % 12) + 1:02d}")
    return out


def _next_month(key: str) -> str:
    y, m = map(int, key.split("-"))
    return f"{y + m // 12}-{m % 12 + 1:02d}"


async def build_analytics(session: AsyncSession, org: Organization, months: int) -> dict[str, Any]:
    all_rows = await finance_rows(session, org.id)
    rows = [r for r in all_rows if r.source != "Анкета"]
    last = rows[-1] if rows else None
    revenue = last.revenue if last else org.revenue
    expenses = last.expenses if last else org.expenses
    debt = last.debt if last else org.debt
    profit = revenue - expenses
    rest = profit - debt

    def delta(key: str) -> str:
        if len(rows) < 2:
            return "Добавьте два соседних месяца для сравнения"
        a, b = rows[-1], rows[-2]
        if _next_month(b.month) != a.month:
            return "Нет данных за предыдущий месяц"

        def val(r: FinanceMonth) -> float:
            if key == "profit":
                return r.revenue - r.expenses
            if key == "rest":
                return r.revenue - r.expenses - r.debt
            return float(getattr(r, key))

        d = val(a) - val(b)
        return f"{'+' if d > 0 else ''}{rub(d)} к предыдущему месяцу"

    by_month = {r.month: r for r in rows}
    series = []
    for key in _window(months):
        r = by_month.get(key)
        series.append(
            {"month": key, "missing": r is None, "revenue": r.revenue if r else None, "expenses": r.expenses if r else None,
             "debt": r.debt if r else None, "profit": (r.revenue - r.expenses) if r else None,
             "rest": (r.revenue - r.expenses - r.debt) if r else None}
        )  # fmt: skip
    window = {s["month"] for s in series}
    table = [
        {"month": r.month, "revenue": r.revenue, "expenses": r.expenses, "profit": r.revenue - r.expenses,
         "debt": r.debt, "rest": r.revenue - r.expenses - r.debt}
        for r in rows if r.month in window
    ]  # fmt: skip

    apps = list(
        (await session.execute(select(Application).where(Application.organization_id == org.id))).scalars()
    )
    groups = []
    for name, statuses in GROUPS:
        xs = [a for a in apps if a.status in statuses]
        groups.append({"name": name, "count": len(xs), "amount": sum(a.amount for a in xs)})

    cash = org.cash_balance
    outflow = expenses + debt
    return {
        "label": f"{last.month}" if last else "Средний месяц по анкете",
        "source": "введенные месячные показатели" if rows else "анкета компании",
        "has_history": bool(rows),
        "base": {
            "revenue": revenue,
            "expenses": expenses,
            "debt": debt,
            "profit": profit,
            "rest": rest,
            "margin": (profit / revenue * 100) if revenue > 0 else None,
        },
        "deltas": {"revenue": delta("revenue"), "profit": delta("profit"), "rest": delta("rest")},
        "months": series,
        "table": table,
        "waterfall": {"revenue": revenue, "expenses": expenses, "debt": debt, "profit": profit, "rest": rest},
        "debt": {
            "debt": debt,
            "share": (debt / revenue * 100) if revenue > 0 else None,
            "cover": (profit / debt) if debt > 0 else None,
        },
        "scenarios": [
            {"pct": p, "value": revenue * (1 + p / 100) - expenses - debt} for p in (-30, -20, -10, 0, 10)
        ],
        "liquidity": {
            "cash_balance": cash,
            "cash_balance_at": org.cash_balance_at,
            "runway": (cash / outflow) if cash is not None and outflow > 0 else None,
            "margin_to_zero": max(0.0, rest / revenue * 100) if revenue > 0 else None,
            "deficit": rest < 0,
        },
        "applications": {"total": len(apps), "groups": groups},
    }
