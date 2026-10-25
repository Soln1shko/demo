"""Денежные потоки, график долга и сценарии Business Twin."""

from __future__ import annotations

from typing import Literal

from financial_intelligence.config import CONFIG, FinancialConfig
from financial_intelligence.schema import (
    CashMonth,
    ForecastMonth,
    ForecastResponse,
    LoanScenario,
    ScenarioResult,
    SimulationRequest,
    SimulationResponse,
)


def loan_payments(loan: LoanScenario | None, months: int) -> list[tuple[int, int]]:
    """Строит аннуитетный график: платёж и остаток основного долга.

    Args:
        loan: Новый кредит или отсутствие кредита.
        months: Длина прогнозного горизонта.

    Returns:
        list[tuple[int, int]]: Платёж и остаток после каждого месяца.
    """
    if loan is None:
        return [(0, 0)] * months
    rate = loan.annual_rate_percent / 1200
    payment = (
        loan.amount / loan.term_months if rate == 0 else loan.amount * rate / (1 - (1 + rate) ** -loan.term_months)
    )
    principal = float(loan.amount)
    schedule = []
    for step in range(months):
        if step >= loan.term_months:
            schedule.append((0, 0))
            continue
        due = principal * rate
        principal_part = min(principal, max(0, payment - due))
        actual_payment = principal_part + due
        principal -= principal_part
        if step == loan.term_months - 1:
            actual_payment += principal
            principal = 0
        schedule.append((round(actual_payment), round(principal)))
    return schedule


def _cash_month(
    month: ForecastMonth,
    loan: LoanScenario | None,
    index: int,
    opening_cash: int,
    payment: int,
    principal: int,
    revenue_multiplier: float,
    expense_multiplier: float,
) -> CashMonth:
    """Применяет одну формулу движения денег ко всем типам траекторий.

    Args:
        month: Базовый прогноз месяца.
        loan: Новый кредит.
        index: Номер месяца в горизонте.
        opening_cash: Остаток перед месяцем.
        payment: Платёж нового кредита.
        principal: Остаток основного долга после платежа.
        revenue_multiplier: Сценарное изменение поступлений.
        expense_multiplier: Сценарное изменение расходов.

    Returns:
        CashMonth: Денежные потоки и остаток на конец месяца.
    """
    ramp = min(1.0, (index + 1) / loan.ramp_months) if loan else 0.0
    revenue = round(month.revenue * revenue_multiplier + (loan.monthly_revenue_effect * ramp if loan else 0))
    expenses = round(month.operating_expenses * expense_multiplier + (loan.monthly_expense_effect if loan else 0))
    taxes = round(month.taxes * revenue_multiplier)
    old_payment = month.existing_debt_payment - (loan.old_payment_reduction if loan else 0)
    disbursement = loan.amount if loan and index == 0 else 0
    investment = loan.investment_amount + loan.old_debt_payoff if loan and index == 0 else 0
    return CashMonth(
        month=month.month,
        revenue=revenue,
        operating_expenses=expenses,
        taxes=taxes,
        existing_debt_payment=old_payment,
        new_loan_payment=payment,
        remaining_principal=principal,
        loan_disbursement=disbursement,
        investment_and_payoff=investment,
        closing_cash=opening_cash + revenue - expenses - taxes - old_payment - payment + disbursement - investment,
    )


def _cash_path(
    forecast: ForecastResponse,
    loan: LoanScenario | None,
    revenue_multiplier: float,
    expense_multiplier: float,
    payments: list[tuple[int, int]],
) -> list[CashMonth]:
    """Считает одну детерминированную денежную траекторию.

    Args:
        forecast: Базовый прогноз.
        loan: Новый кредит.
        revenue_multiplier: Множитель поступлений.
        expense_multiplier: Множитель расходов.
        payments: График кредита.

    Returns:
        list[CashMonth]: Помесячные результаты.
    """
    cash = forecast.opening_cash
    path = []
    for index, (month, (payment, principal)) in enumerate(zip(forecast.months, payments, strict=True)):
        result = _cash_month(month, loan, index, cash, payment, principal, revenue_multiplier, expense_multiplier)
        path.append(result)
        cash = result.closing_cash
    return path


def simulate_finances(request: SimulationRequest, config: FinancialConfig = CONFIG) -> SimulationResponse:
    """Считает денежные траектории бизнеса с кредитом или без него.

    Args:
        request: Прогноз и необязательный кредит.
        config: Финансовые допущения.

    Returns:
        SimulationResponse: Детерминированные денежные пути.

    Raises:
        ValueError: В рефинансировании старый платёж меньше заявленного снижения.
    """
    forecast = request.forecast
    loan = request.loan
    if loan and loan.old_payment_reduction > min(item.existing_debt_payment for item in forecast.months):
        raise ValueError("Снижение старого платежа превышает действующий платёж.")
    payments = loan_payments(loan, len(forecast.months))
    variants: tuple[tuple[Literal["base", "optimistic", "stress"], float, float], ...] = (
        ("base", 1.0, 1.0),
        ("optimistic", config.optimistic_revenue_multiplier, 1.0),
        ("stress", config.stress_revenue_multiplier, config.stress_expense_multiplier),
    )
    scenarios = []
    for name, revenue_multiplier, expense_multiplier in variants:
        path = _cash_path(forecast, loan, revenue_multiplier, expense_multiplier, payments)
        scenarios.append(
            ScenarioResult(
                name=name, months=path, minimum_cash=min(forecast.opening_cash, *(item.closing_cash for item in path))
            )
        )
    return SimulationResponse(
        company_id=forecast.company_id,
        has_loan=loan is not None,
        monthly_payment=payments[0][0],
        scenarios=scenarios,
    )
