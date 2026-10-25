"""Скоринг (оценка риска) и кредитное решение.

Скоринг и решение намеренно разделены: скоринг даёт балл и факторы, решение
учитывает ещё продукт, сумму, срок, внешние проверки и правила банка.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.domain.finance import ProductSpec


class ScoringRules(BaseModel):
    """Параметры демомодели. Хранятся в БД, изменяются администратором."""

    version: int = 1
    base_score: int = Field(92, ge=0, le=100)
    load_high: float = Field(0.7, gt=0, le=2)
    load_mid: float = Field(0.4, gt=0, le=2)
    penalty_load_high: int = Field(35, ge=0, le=100)
    penalty_load_mid: int = Field(18, ge=0, le=100)
    penalty_load_low: int = Field(4, ge=0, le=100)
    penalty_late: int = Field(40, ge=0, le=100)
    penalty_young: int = Field(20, ge=0, le=100)
    review_below: int = Field(50, ge=0, le=100)
    alt_load_limit: float = Field(0.6, gt=0, le=2)
    alt_flow_share: float = Field(0.4, gt=0, le=1)
    alt_step: int = Field(10_000, ge=1_000)


@dataclass
class RiskInputs:
    amount: float
    revenue: float
    expenses: float
    debt: float
    age: int
    late: bool


@dataclass
class ExternalSignals:
    """Сигналы от (смоделированных) ФНС и БКИ."""

    fns_active: bool = True
    fns_note: str = ""
    bki_overdue: bool = False
    bki_note: str = ""


@dataclass
class Factor:
    code: str
    title: str
    delta: int
    detail: str


@dataclass
class RiskResult:
    pay: float
    cash: float
    load: float
    score: int
    result: str  # approved | alternative | review | rejected
    alt: float
    factors: list[Factor] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    rules_version: int = 1


def _round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def safe_alt_amount(
    p: ProductSpec, rules: ScoringRules, cash: float, debt: float, pay: float, amount: float
) -> float:
    """Посильная сумма: платежи не больше доли свободного потока, шаг округления alt_step."""
    if pay <= 0 or amount <= 0:
        return 0.0
    per_ruble = pay / amount
    budget = max(0.0, cash * rules.alt_flow_share - debt)
    value = math.floor(budget / per_ruble / rules.alt_step) * rules.alt_step
    return float(min(p.max_amount, value))


def assess(
    p: ProductSpec,
    inputs: RiskInputs,
    peak_payment: float,
    rules: ScoringRules,
    signals: ExternalSignals | None = None,
) -> RiskResult:
    signals = signals or ExternalSignals()
    cash = inputs.revenue - inputs.expenses
    load = (peak_payment + inputs.debt) / max(1.0, cash)
    late = inputs.late or signals.bki_overdue

    factors: list[Factor] = [Factor("base", "Базовый балл", rules.base_score, "Начальная оценка модели")]
    if load > rules.load_high:
        penalty, band = rules.penalty_load_high, f"выше {rules.load_high:.0%}"
    elif load > rules.load_mid:
        penalty, band = rules.penalty_load_mid, f"от {rules.load_mid:.0%} до {rules.load_high:.0%}"
    else:
        penalty, band = rules.penalty_load_low, f"до {rules.load_mid:.0%}"
    factors.append(Factor("load", "Платёжная нагрузка", -penalty, f"Нагрузка {load:.1%} — {band}"))
    if late:
        source = "по БКИ" if signals.bki_overdue and not inputs.late else "по данным заявки"
        factors.append(
            Factor("late", "Просроченная задолженность", -rules.penalty_late, f"Просрочка {source}")
        )
    if inputs.age < p.min_age:
        factors.append(
            Factor(
                "age",
                "Возраст бизнеса",
                -rules.penalty_young,
                f"Менее {p.min_age} мес. при минимуме для продукта",
            )
        )

    score = max(0, min(100, sum(f.delta for f in factors)))
    score = _round_half_up(score)
    alt = safe_alt_amount(p, rules, cash, inputs.debt, peak_payment, inputs.amount)

    reasons: list[str] = []
    if not signals.fns_active:
        result = "rejected"
        reasons.append(signals.fns_note or "Компания не действует по данным ФНС")
    elif late or cash <= 0:
        result = "rejected"
        reasons.append(
            "Есть текущая просроченная задолженность"
            if late
            else "Расходы не оставляют положительного денежного потока"
        )
    elif score < rules.review_below or inputs.age < p.min_age:
        result = "review"
        reasons.append("Автоматической оценки недостаточно — нужен эксперт")
    elif load > rules.alt_load_limit or inputs.amount > p.max_amount:
        if alt < p.min_amount:
            result = "rejected"
            reasons.append("Безопасная сумма ниже минимального лимита продукта")
        else:
            result = "alternative"
            reasons.append("Платёж слишком велик для свободного потока или превышен лимит продукта")
    else:
        result = "approved"
        reasons.append("Правила решения пройдены")

    return RiskResult(
        pay=peak_payment,
        cash=cash,
        load=load,
        score=score,
        result=result,
        alt=alt,
        factors=factors,
        reasons=reasons,
        rules_version=rules.version,
    )
