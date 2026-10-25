"""Поведенческие кейсы цифрового двойника и кредитного квеста."""

from datetime import date

from financial_intelligence.demo import demo_case
from financial_intelligence.forecast import forecast_financials
from financial_intelligence.quest import generate_quest, recalculate_quest
from financial_intelligence.schema import ForecastRequest, LoanScenario, RecalculateRequest, SimulationRequest
from financial_intelligence.simulation import loan_payments, simulate_finances
from scoring import ScoringEngine


def test_credit_without_investment_effect_reduces_cash_by_payments() -> None:
    """Выдача и вложение гасят друг друга; без отдачи остаются платежи."""
    case = demo_case("stable")
    forecast = forecast_financials(case.forecast_request)
    loan = case.loan.model_copy(update={"monthly_revenue_effect": 0, "monthly_expense_effect": 0})
    without = simulate_finances(SimulationRequest(forecast=forecast))
    with_loan = simulate_finances(SimulationRequest(forecast=forecast, loan=loan))
    without_end = without.scenarios[0].months[-1].closing_cash
    with_end = with_loan.scenarios[0].months[-1].closing_cash
    assert not without.has_loan and with_loan.has_loan
    assert with_end == without_end - sum(month.new_loan_payment for month in with_loan.scenarios[0].months)
    assert with_loan.scenarios[0].months[0].loan_disbursement == loan.amount
    assert with_loan.scenarios[0].months[0].investment_and_payoff == loan.amount


def test_rate_and_term_change_cash_and_total_repayment() -> None:
    """Ставка и срок меняют платежи; длинный срок дороже за весь срок."""
    case = demo_case("stable")
    forecast = forecast_financials(case.forecast_request)
    standard = simulate_finances(SimulationRequest(forecast=forecast, loan=case.loan))
    cheaper_loan = case.loan.model_copy(update={"annual_rate_percent": 8})
    cheaper = simulate_finances(SimulationRequest(forecast=forecast, loan=cheaper_loan))
    longer_loan = case.loan.model_copy(update={"term_months": 60})
    longer = simulate_finances(SimulationRequest(forecast=forecast, loan=longer_loan))
    assert cheaper.monthly_payment < standard.monthly_payment
    assert cheaper.scenarios[0].months[-1].closing_cash > standard.scenarios[0].months[-1].closing_cash
    assert longer.monthly_payment < standard.monthly_payment
    assert sum(payment for payment, _ in loan_payments(longer_loan, 60)) > sum(
        payment for payment, _ in loan_payments(case.loan, 36)
    )


def test_no_sales_does_not_erase_fixed_expenses() -> None:
    """Нулевая выручка не превращает постоянные расходы в ноль."""
    cash = 600000
    history = []
    for month in range(1, 7):
        cash -= 110000
        history.append(
            {
                "month": date(2025, month, 1),
                "revenue": 0,
                "operating_expenses": 100000,
                "taxes": 10000,
                "existing_debt_payment": 0,
                "cash_balance": cash,
            }
        )
    forecast = forecast_financials(
        ForecastRequest.model_validate(
            {"company_id": "demo_zero_sales", "industry": "услуги", "business_age_months": 12, "history": history}
        )
    )
    assert all(
        month.revenue == 0 and month.operating_expenses == 100000 and month.taxes == 10000 for month in forecast.months
    )
    result = simulate_finances(SimulationRequest(forecast=forecast))
    assert result.scenarios[0].months[0].closing_cash == cash - 110000


def test_refinancing_replaces_old_payment_without_double_counting() -> None:
    """Рефинансирование закрывает долг и заменяет часть старого платежа."""
    case = demo_case("stable")
    forecast = forecast_financials(case.forecast_request)
    refinancing = LoanScenario(
        amount=1000000,
        term_months=36,
        annual_rate_percent=18,
        purpose="refinancing",
        old_debt_payoff=1000000,
        old_payment_reduction=90000,
    )
    without = simulate_finances(SimulationRequest(forecast=forecast))
    with_refinancing = simulate_finances(SimulationRequest(forecast=forecast, loan=refinancing))
    first = with_refinancing.scenarios[0].months[0]
    assert first.loan_disbursement == first.investment_and_payoff == 1000000
    assert first.existing_debt_payment == 0
    assert first.closing_cash - without.scenarios[0].months[0].closing_cash == 90000 - first.new_loan_payment


def test_quest_keeps_cash_viable_and_recalculation_matches_plan() -> None:
    """Квест не скрывает отрицательный остаток и не ухудшает его без предупреждения."""
    case = demo_case("risky")
    scoring = ScoringEngine.from_json()
    forecast = forecast_financials(case.forecast_request)
    baseline = simulate_finances(SimulationRequest(forecast=forecast, loan=case.loan)).scenarios[0].minimum_cash
    result = generate_quest(case, scoring)
    assert result.plans
    for plan in result.plans:
        assert plan.projected_score > result.baseline_score
        assert plan.minimum_cash >= baseline
        assert not plan.target_reached
        recalculated = recalculate_quest(
            RecalculateRequest.model_validate(
                {**case.model_dump(mode="json"), "actions": [a.model_dump() for a in plan.actions]}
            ),
            scoring,
        )
        assert recalculated.plan == plan
        assert recalculated.simulation.scenarios[0].minimum_cash == plan.minimum_cash
        if any(action.type == "reduce_monthly_expenses" for action in plan.actions):
            assert [month.operating_expenses for month in recalculated.forecast.months[:3]] == [
                month.operating_expenses for month in forecast.months[:3]
            ]
            assert recalculated.forecast.months[3].operating_expenses < forecast.months[3].operating_expenses
