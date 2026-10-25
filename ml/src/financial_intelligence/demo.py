"""Три воспроизводимых синтетических бизнеса для демонстрации."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date
from typing import Literal

from financial_intelligence.schema import ForecastRequest, LoanScenario, QuestRequest

DemoKind = Literal["stable", "seasonal", "risky"]


@dataclass(frozen=True, slots=True)
class DemoProfile:
    """Параметры воспроизводимого синтетического бизнеса.

    Attributes:
        industry: Отрасль.
        base_revenue: Выручка первого месяца.
        expense_ratio: Доля операционных расходов.
        tax_ratio: Доля налогов.
        debt_payment: Старый месячный платёж.
        opening_cash: Остаток перед первым месяцем истории.
        monthly_trend: Среднемесячный тренд выручки.
        credit_history_score: Синтетическая оценка кредитной истории.
        debt_ratio: Отношение старого долга к месячной выручке.
        loan_amount: Сумма нового кредита.
    """

    industry: str
    base_revenue: int
    expense_ratio: float
    tax_ratio: float
    debt_payment: int
    opening_cash: int
    monthly_trend: float
    credit_history_score: int
    debt_ratio: float
    loan_amount: int


PROFILES: dict[DemoKind, DemoProfile] = {
    "stable": DemoProfile(
        industry="услуги",
        base_revenue=1400000,
        expense_ratio=0.66,
        tax_ratio=0.055,
        debt_payment=90000,
        opening_cash=1400000,
        monthly_trend=0.006,
        credit_history_score=790,
        debt_ratio=0.5,
        loan_amount=3000000,
    ),
    "seasonal": DemoProfile(
        industry="кафе",
        base_revenue=1200000,
        expense_ratio=0.7,
        tax_ratio=0.05,
        debt_payment=100000,
        opening_cash=1000000,
        monthly_trend=0.002,
        credit_history_score=690,
        debt_ratio=1.2,
        loan_amount=2500000,
    ),
    "risky": DemoProfile(
        industry="торговля",
        base_revenue=800000,
        expense_ratio=0.84,
        tax_ratio=0.04,
        debt_payment=130000,
        opening_cash=900000,
        monthly_trend=-0.004,
        credit_history_score=520,
        debt_ratio=2.4,
        loan_amount=2000000,
    ),
}


def demo_case(kind: DemoKind, seed: int = 20261023) -> QuestRequest:
    """Создаёт финансовую историю и согласованную кредитную заявку.

    Args:
        kind: Устойчивый, сезонный или рискованный профиль.
        seed: Начальное состояние генератора.

    Returns:
        QuestRequest: Готовый сценарий для четырёх методов API.
    """
    profile = PROFILES[kind]
    randomizer = random.Random(seed)
    cash = profile.opening_cash
    history = []
    for index in range(24):
        month = date(2024 + index // 12, index % 12 + 1, 1)
        seasonal = 1 + (0.28 * math.sin(2 * math.pi * index / 12) if kind == "seasonal" else 0)
        revenue = max(
            0,
            round(
                profile.base_revenue * (1 + profile.monthly_trend) ** index * seasonal * randomizer.uniform(0.96, 1.04)
            ),
        )
        expenses = round(revenue * profile.expense_ratio)
        taxes = round(revenue * profile.tax_ratio)
        cash += revenue - expenses - taxes - profile.debt_payment
        history.append(
            {
                "month": month,
                "revenue": revenue,
                "operating_expenses": expenses,
                "taxes": taxes,
                "existing_debt_payment": profile.debt_payment,
                "cash_balance": cash,
            }
        )
    forecast = ForecastRequest.model_validate(
        {
            "company_id": f"demo_{kind}",
            "industry": profile.industry,
            "business_age_months": 36,
            "history": history,
            "horizon_months": 12,
        }
    )
    loan = LoanScenario(
        amount=profile.loan_amount,
        term_months=36,
        annual_rate_percent=18,
        purpose="development",
        investment_amount=profile.loan_amount,
        monthly_revenue_effect=round(profile.loan_amount * 0.06),
        monthly_expense_effect=round(profile.loan_amount * 0.01),
        ramp_months=6,
    )
    last_revenue = forecast.history[-1].revenue
    return QuestRequest.model_validate(
        {
            "forecast_request": forecast.model_dump(mode="json"),
            "scoring": {
                "product_id": "business_loan",
                "requested_amount": profile.loan_amount,
                "term_months": loan.term_months,
                "business_age_months": 36,
                "monthly_revenue": last_revenue,
                "net_margin_percent": round((1 - profile.expense_ratio - profile.tax_ratio) * 100, 2),
                "debt_to_revenue_ratio": profile.debt_ratio,
                "has_overdue_debt": kind == "risky",
                "credit_history_score": profile.credit_history_score,
                "has_collateral": False,
                "legal_form": "ooo" if kind == "seasonal" else "ip",
            },
            "loan": loan.model_dump(),
            "target_score": 70,
            "existing_debt_balance": round(last_revenue * profile.debt_ratio),
            "minimum_acceptable_amount": round(profile.loan_amount * 0.5),
        }
    )
