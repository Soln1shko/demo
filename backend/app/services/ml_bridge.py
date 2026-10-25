"""Снимок организации/заявки в контракт ML и поиск суммы под оценку одобрения."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.integrations import ml
from app.models import Application, ExternalCheck, Organization

TARGET_APPROVAL = 80


def case_id(raw: str) -> str:
    token = re.sub(r"[^A-Z0-9-]", "", raw.upper())[:16] or "CASE"
    return f"DEMO-{token}"[:29]


def legal_form(value: str | None) -> str:
    return "ip" if (value or "").lower() == "ip" else "ooo"


def margin(revenue: float, expenses: float) -> float:
    if revenue <= 0:
        return 0.0
    return max(0.0, min(100.0, (revenue - expenses) / revenue * 100))


def debt_ratio(debt: float, revenue: float) -> float:
    if revenue <= 0:
        return 0.0
    return max(0.0, debt / revenue)


def credit_history(late: bool) -> int:
    return 580 if late else 720


def purpose_of(goal: str, category: str = "") -> str:
    text = f"{goal} {category}".lower()
    if any(word in text for word in ("разрыв", "касс", "платеж", "овердрафт")):
        return "cash_gap"
    if any(word in text for word in ("недвиж", "оборуд", "инвест", "авто")):
        return "investment"
    return "working_capital"


def scoring_body(
    product_id: str,
    amount: float,
    months: int,
    org: Organization | None = None,
    app: Application | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = app or org
    revenue = float(getattr(source, "revenue", 0) or 0)
    expenses = float(getattr(source, "expenses", 0) or 0)
    debt = float(getattr(source, "debt", 0) or 0)
    age = int(getattr(source, "age", 0) or 0)
    late = bool(getattr(source, "late", False))
    legal = legal_form(getattr(source, "legal", "ooo"))
    collateral = getattr(org, "collateral", "no") if org is not None else "no"
    if app is not None:
        collateral = "yes" if app.product_snapshot.get("secured") else collateral
    patch = extra or {}
    return {
        "product_id": product_id,
        "requested_amount": max(1, int(patch.get("requested_amount", amount))),
        "term_months": max(1, int(patch.get("term_months", months))),
        "business_age_months": max(0, int(patch.get("business_age_months", age))),
        "monthly_revenue": max(0, int(patch.get("monthly_revenue", revenue))),
        "net_margin_percent": float(patch.get("net_margin_percent", margin(revenue, expenses))),
        "debt_to_revenue_ratio": float(patch.get("debt_to_revenue_ratio", debt_ratio(debt, revenue))),
        "has_overdue_debt": bool(patch.get("has_overdue_debt", late)),
        "credit_history_score": int(patch.get("credit_history_score", credit_history(late))),
        "has_collateral": bool(patch.get("has_collateral", collateral not in ("", "no", None))),
        "legal_form": patch.get("legal_form") or legal,
    }


def advisor_body(org: Organization, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    patch = extra or {}
    score = scoring_body(
        "business_loan",
        float(patch.get("requested_amount", org.amount or 1_000_000)),
        int(patch.get("term_months", org.months or 24)),
        org=org,
        extra=patch,
    )
    score.pop("product_id")
    purpose = patch.get("purpose") or purpose_of(org.goal)
    return {
        **score,
        "purpose": purpose,
        "has_marketplace_sales": bool(patch.get("has_marketplace_sales", org.profile == "retail")),
        "has_existing_business_loans": bool(patch.get("has_existing_business_loans", org.debt > 0)),
        "context_tags": list(patch.get("context_tags") or (purpose,)),
        "top_n": int(patch.get("top_n", 3)),
    }


def cash_gap_body(org: Organization) -> dict[str, Any]:
    revenue = max(0, int(org.revenue))
    expenses = max(0, int(org.expenses))
    cash = org.cash_balance
    opening = max(0, int(cash)) if cash is not None else max(0, revenue - expenses)
    delay = {"retail": 7, "services": 18, "production": 28}.get(org.profile, 14)
    return {
        "monthly_revenue": revenue,
        "net_margin_percent": margin(revenue, expenses),
        "opening_balance": opening,
        # cash_cap сам считает переменные списания как выручка × (1 − маржа),
        # то есть уже включает расходы в пределах выручки. Здесь только долг
        # и превышение расходов над выручкой, чтобы не считать их дважды.
        "monthly_fixed_costs": max(0, expenses - revenue) + max(0, int(org.debt)),
        "sales_volatility": 0.15 if org.seasonality == "stable" else 0.4,
        "payment_delay_days": delay,
        "upcoming_expenses": 0,
        "forecast_days": 30,
    }


def nba_body(org: Organization) -> dict[str, Any]:
    return {
        "legal_form": legal_form(org.legal),
        "business_age_months": max(0, org.age),
        "monthly_turnover": max(0, int(org.revenue)),
        "monthly_payment_count": 40 if org.profile == "retail" else 20,
        "online_sales_share": 0.6 if org.profile == "retail" else 0.2,
        "has_business_account": True,
        "has_website": org.profile != "production",
        "has_offline_point": org.profile in ("retail", "production"),
        "sells_on_marketplaces": org.profile == "retail",
        "employee_count": 8 if org.legal == "ooo" else 2,
        "has_foreign_trade": False,
        "needs_tax_reporting": True,
        "uses_electronic_documents": True,
        "wants_business_registration": org.age < 6,
        "existing_product_ids": ["business_account"],
        "top_n": 3,
    }


def approval_pct(result: dict[str, Any] | None) -> int | None:
    """Условная обратная шкала риска; старое имя поля API не означает вероятность решения банка."""
    if not result or "risk_probability" not in result:
        return None
    return max(0, min(100, round((1 - float(result["risk_probability"])) * 100)))


def classify(risk_probability: float, amount: float, revenue: float) -> tuple[str, str]:
    """Локальные правила underwriting: сложность разбора и срочность для аналитика."""
    if risk_probability >= 0.65:
        complexity = "high"
    elif risk_probability >= 0.35:
        complexity = "medium"
    else:
        complexity = "low"
    months = amount / revenue if revenue > 0 else 99
    if months >= 4 or risk_probability >= 0.65:
        priority = "high"
    elif months >= 2 or risk_probability >= 0.35:
        priority = "medium"
    else:
        priority = "low"
    return complexity, priority


async def live_score(
    product_id: str, amount: float, months: int, org: Organization, extra: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    result = await ml.score(scoring_body(product_id, amount, months, org=org, extra=extra))
    if result is None:
        return None
    pct = approval_pct(result)
    complexity, priority = classify(float(result.get("risk_probability", 0)), amount, org.revenue)
    return {**result, "approval_pct": pct, "complexity": complexity, "priority": priority}


async def amount_for_approval(
    product_id: str, org: Organization, months: int, lo: int, hi: int, extra: dict[str, Any] | None = None
) -> tuple[int, int] | None:
    """Ищет наибольшую сумму в диапазоне с условной оценкой модели не ниже 80."""
    best: tuple[int, int] | None = None
    low, high = max(1, lo), max(lo, hi)
    for _ in range(14):
        mid = (low + high) // 2
        scored = await live_score(product_id, mid, months, org, extra)
        if scored is None:
            return best
        pct = int(scored["approval_pct"])
        if pct >= TARGET_APPROVAL:
            best = (mid, pct)
            low = mid + 1
        else:
            high = mid - 1
        if low > high:
            break
    return best


def underwriting_request(
    app: Application, scoring: dict[str, Any], checks: list[ExternalCheck]
) -> dict[str, Any]:
    revenue = max(0, int(app.revenue))
    mapped: list[dict[str, Any]] = []
    for item in checks:
        status = "flag" if item.payload.get("overdue") or item.payload.get("risk_flags") else "clear"
        mapped.append(
            {
                "check_id": item.source,
                "label": "ФНС" if item.source == "fns" else "БКИ",
                "status": status,
                "details": str(
                    item.payload.get("status_text") or item.payload.get("discipline") or item.source
                ),
                "source": item.source,
            }
        )
    return {
        "case_id": case_id(app.id),
        "business": {
            "segment": "micro" if app.revenue < 2_000_000 else "small",
            "legal_form": legal_form(app.legal),
            "business_age_months": max(0, app.age),
            "industry": app.region or "торговля",
        },
        "application": {
            "product_id": app.product_id,
            "requested_amount": max(1, int(app.amount)),
            "term_months": max(1, app.months),
            "purpose": purpose_of(app.goal, app.product_snapshot.get("category", "")),
        },
        "financials": {
            "monthly_revenue": revenue,
            "net_margin_percent": margin(app.revenue, app.expenses),
            "debt_to_revenue_ratio": debt_ratio(app.debt, app.revenue),
        },
        "scoring": {
            "risk_probability": scoring.get("risk_probability", 0),
            "risk_band": scoring.get("risk_band", "unknown"),
            "factors": scoring.get("factors") or [],
            "model_version": scoring.get("model_version", "cabinet"),
        },
        "checks": mapped,
        "additional_facts": [],
    }


INDUSTRY = {"retail": "торговля", "services": "услуги", "production": "производство"}


def demo_company_id(org: Organization) -> str:
    token = re.sub(r"[^a-z0-9]", "", org.id.lower())[:28] or "org"
    return f"demo_{token}"


def _shift_month(key: str, delta: int) -> str:
    year, month = map(int, key.split("-"))
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year}-{month:02d}"


def finance_history(rows: list[Any], org: Organization) -> list[dict[str, Any]]:
    """6–12 последовательных месяцев: живая история или синтетика из анкеты."""
    real = [row for row in rows if getattr(row, "source", "") != "Анкета"]
    keyed = {row.month: row for row in real}
    streak: list[Any] = []
    if real:
        cursor = real[-1].month
        while cursor in keyed:
            streak.append(keyed[cursor])
            cursor = _shift_month(cursor, -1)
        streak.reverse()
    if len(streak) >= 6:
        used = [(row.month, row.revenue, row.expenses, row.debt) for row in streak[-12:]]
    else:
        end = streak[-1].month if streak else date.today().strftime("%Y-%m")
        by = {row.month: row for row in streak}
        used = []
        for index, key in enumerate(_shift_month(end, i - 5) for i in range(6)):
            row = by.get(key)
            if row is None:
                used.append(
                    (key, org.revenue * (0.88 + index * 0.02), org.expenses * (0.9 + index * 0.015), org.debt)
                )
            else:
                used.append((key, row.revenue, row.expenses, row.debt))
        used[-1] = (used[-1][0], org.revenue, org.expenses, org.debt)
    # История заканчивается текущим остатком. Не прибавляем прошлые месяцы к сегодняшним деньгам.
    current_cash = (
        int(org.cash_balance)
        if org.cash_balance is not None
        else max(0, round(org.revenue - org.expenses - org.debt))
    )
    running = current_cash - sum(round(revenue - expenses - debt) for _, revenue, expenses, debt in used)
    history = []
    for month_key, raw_revenue, raw_expenses, raw_debt in used:
        revenue = max(0, int(round(raw_revenue)))
        expenses = max(0, int(round(raw_expenses)))
        debt_pay = max(0, int(round(raw_debt)))
        running = running + revenue - expenses - debt_pay
        history.append(
            {
                "month": f"{month_key}-01",
                "revenue": revenue,
                "operating_expenses": expenses,
                "taxes": 0,
                "existing_debt_payment": debt_pay,
                "cash_balance": running,
            }
        )
    return history


def forecast_request(org: Organization, rows: list[Any]) -> dict[str, Any]:
    return {
        "company_id": demo_company_id(org),
        "industry": INDUSTRY.get(org.profile, "торговля"),
        "business_age_months": max(0, org.age),
        "history": finance_history(rows, org),
        "horizon_months": 6,
    }


def loan_of(org: Organization) -> dict[str, Any]:
    purpose = purpose_of(org.goal)
    amount = max(1, int(org.amount or 1_000_000))
    months = max(1, min(120, int(org.months or 24)))
    if purpose == "investment":
        return {
            "amount": amount,
            "term_months": months,
            "annual_rate_percent": 16.5,
            "purpose": "development",
            "investment_amount": amount,
            "monthly_revenue_effect": max(0, int(amount * 0.03)),
            "monthly_expense_effect": 0,
            "ramp_months": 3,
        }
    if purpose == "cash_gap":
        return {"amount": amount, "term_months": months, "annual_rate_percent": 18.0, "purpose": "cash_gap"}
    return {
        "amount": amount,
        "term_months": months,
        "annual_rate_percent": 16.5,
        "purpose": "working_capital",
    }


def quest_request(org: Organization, rows: list[Any]) -> dict[str, Any]:
    history = finance_history(rows, org)
    score = scoring_body(
        "business_loan",
        org.amount or 1_000_000,
        org.months or 24,
        org=org,
        extra={"monthly_revenue": history[-1]["revenue"]},
    )
    loan = loan_of(org)
    loan["amount"] = score["requested_amount"]
    loan["term_months"] = score["term_months"]
    return {
        "forecast_request": {
            "company_id": demo_company_id(org),
            "industry": INDUSTRY.get(org.profile, "торговля"),
            "business_age_months": score["business_age_months"],
            "history": history,
            "horizon_months": 6,
        },
        "scoring": score,
        "loan": loan,
        "target_score": 70,
        "existing_debt_balance": max(0, int(org.debt * 12)),
        "minimum_acceptable_amount": max(1, score["requested_amount"] // 2),
    }


def recovery_body(app: Application, org: Organization, product_ids: list[str]) -> dict[str, Any]:
    profile = advisor_body(org, {"requested_amount": int(app.amount), "term_months": app.months})
    profile.pop("top_n", None)
    profile.pop("context_tags", None)
    return {
        "case_id": case_id(app.id),
        "profile": profile,
        "declined_offers": [
            {
                "product_id": app.product_id,
                "requested_amount": max(1, int(app.amount)),
                "term_months": max(1, app.months),
                "reasons": [app.comment or "Предварительная оценка риска высокая."],
            }
        ],
        "recommended_product_ids": product_ids[:8],
        "minimum_acceptable_amount": max(1, int(app.amount) // 2),
        "minimum_acceptable_term_months": max(1, max(1, app.months // 2)),
    }


def copilot_body(
    ticket_id: str, question: str, messages: list[Any], org: Organization | None, app: Application | None
) -> dict[str, Any]:
    history = []
    for index, message in enumerate(messages):
        author = "employee" if getattr(message, "author_role", "") == "bank" else "customer"
        history.append(
            {
                "message_id": f"msg-{getattr(message, 'id', index + 1)}",
                "author": author,
                "text": (getattr(message, "text", None) or question)[:2000],
            }
        )
    if not history:
        history = [{"message_id": "msg-1", "author": "customer", "text": question[:2000]}]
    body: dict[str, Any] = {
        "case_id": case_id(ticket_id),
        "customer_question": question[:2000],
        "history": history[:50],
    }
    if app is not None:
        decision = "pending"
        if app.status in ("approved", "signed", "funded"):
            decision = "approved"
        elif app.status == "rejected":
            decision = "declined"
        body["application"] = {
            "status": app.status,
            "product_id": app.product_id,
            "requested_amount": max(1, int(app.amount)),
            "term_months": max(1, app.months),
            "purpose": purpose_of(app.goal),
            "decision": decision,
            "decision_reason": (app.comment or None),
        }
    if org is not None:
        body["profile"] = {
            "legal_form": legal_form(org.legal),
            "industry": INDUSTRY.get(org.profile, "торговля"),
            "business_age_months": max(0, org.age),
            "monthly_revenue": max(0, int(org.revenue)),
            "monthly_expenses": max(0, int(org.expenses)),
            "net_margin_percent": margin(org.revenue, org.expenses),
            "existing_debt_balance": max(0, int(org.debt * 12)),
            "monthly_debt_payment": max(0, int(org.debt)),
        }
    return body


def compact_simulation(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return {
        "monthly_payment": raw.get("monthly_payment"),
        "scenarios": [
            {
                "name": item.get("name"),
                "minimum_cash": item.get("minimum_cash"),
                "closing_cash": (item.get("months") or [{}])[-1].get("closing_cash"),
                "remaining_principal": (item.get("months") or [{}])[-1].get("remaining_principal"),
            }
            for item in raw.get("scenarios") or []
        ],
    }
