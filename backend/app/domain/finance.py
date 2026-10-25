"""Финансовая математика: аннуитет, дифференцированные и «единым платежом» графики."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


@dataclass(frozen=True)
class ProductSpec:
    id: str
    name: str
    kind: str  # loan | line | overdraft | daily
    scheme: str  # annuity | diff | bullet
    secured: bool
    category: str
    min_amount: float
    max_amount: float
    min_months: int
    max_months: int
    min_age: int
    rate: float
    daily: float | None = None


@dataclass
class QuoteInput:
    amount: float
    months: int = 12
    days: int = 30
    rate: float = 0.0
    scheme: str = "annuity"
    fee: float = 0.0


@dataclass
class ScheduleRow:
    n: int
    payment: float
    principal: float
    interest: float
    balance: float


@dataclass
class QuoteResult:
    interest: float
    total: float
    cost: float
    rows: list[ScheduleRow] = field(default_factory=list)
    first: float = 0.0
    last: float = 0.0
    peak: float = 0.0
    monthly: float = 0.0


def annuity_payment(amount: float, months: int, rate_pct: float) -> float:
    """Аннуитетный платёж. rate_pct — годовая ставка в процентах."""
    r = rate_pct / 1200
    if months <= 0:
        return amount
    if r == 0:
        return amount / months
    return amount * r / (1 - (1 + r) ** -months)


def default_quote_input(p: ProductSpec, amount: float, months: int) -> QuoteInput:
    return QuoteInput(
        amount=amount,
        months=months,
        days=30,
        rate=p.daily if p.daily is not None else p.rate,
        scheme=p.scheme,
        fee=0.0,
    )


def quote_error(p: ProductSpec, q: QuoteInput) -> str | None:
    """Возвращает текст ошибки валидации расчёта или None."""
    if not isfinite(q.amount) or q.amount < p.min_amount or q.amount > p.max_amount:
        return f"Сумма должна быть от {_rub(p.min_amount)} до {_rub(p.max_amount)}."
    if p.kind == "overdraft":
        if int(q.days) != q.days or q.days < 1 or q.days > 60:
            return "Укажите от 1 до 60 дней."
    elif int(q.months) != q.months or q.months < p.min_months or q.months > p.max_months:
        return f"Срок от {p.min_months} до {p.max_months} месяцев."
    limit = 3 if p.daily is not None else 150
    if not isfinite(q.rate) or q.rate < 0 or q.rate > limit or q.fee < 0:
        return "Проверьте ставку и стоимость услуг."
    return None


def quote_math(p: ProductSpec, q: QuoteInput) -> QuoteResult:
    amount, months, rate = float(q.amount), int(q.months), float(q.rate)
    interest = 0.0
    rows: list[ScheduleRow] = []
    balance = amount
    daily = p.kind == "daily"
    overdraft = p.kind == "overdraft"

    if overdraft:
        interest = amount * rate / 100 * q.days / 365
        rows = [ScheduleRow(int(q.days), amount + interest, amount, interest, 0.0)]
    elif q.scheme == "bullet" or daily:
        for i in range(months):
            v = amount * (rate / 100 * 30 if daily else rate / 1200)
            interest += v
            last = i == months - 1
            rows.append(
                ScheduleRow(
                    i + 1, v + (amount if last else 0), amount if last else 0.0, v, 0.0 if last else amount
                )
            )
    else:
        pay = annuity_payment(amount, months, rate)
        for i in range(months):
            iv = balance * rate / 1200
            pr = amount / months if q.scheme == "diff" else min(balance, pay - iv)
            balance = max(0.0, balance - pr)
            interest += iv
            rows.append(ScheduleRow(i + 1, pr + iv, pr, iv, balance))

    fee = q.fee if isfinite(q.fee) else 0.0
    payments = [r.payment for r in rows] or [0.0]
    return QuoteResult(
        interest=interest,
        total=amount + interest + fee,
        cost=interest + fee,
        rows=rows,
        first=rows[0].payment if rows else 0.0,
        last=rows[-1].payment if rows else 0.0,
        peak=max(payments),
        monthly=interest if overdraft else (rows[0].payment if rows else 0.0),
    )


def _rub(n: float) -> str:
    return f"{round(n):,}".replace(",", "\u00a0") + " ₽"
