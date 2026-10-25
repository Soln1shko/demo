"""Сквозные финансовые инварианты Business Twin и Credit Quest."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from financial_intelligence.demo import demo_case
from financial_intelligence.forecast import forecast_financials, rolling_backtest
from financial_intelligence.quest import generate_quest, recalculate_quest
from financial_intelligence.schema import (
    ForecastRequest,
    LoanScenario,
    QuestRequest,
    RecalculateRequest,
    SimulationRequest,
)
from financial_intelligence.simulation import simulate_finances
from scoring import ScoringEngine
from tests.test_api import FakeAssistant, FakeLlm, FakeOcr


def _inputs() -> tuple[ForecastRequest, LoanScenario, QuestRequest]:
    history = []
    cash = 500000
    for index in range(12):
        revenue = 900000 + index * 15000
        cash += revenue - 720000 - 40000 - 100000
        history.append(
            {
                "month": date(2025, index + 1, 1),
                "revenue": revenue,
                "operating_expenses": 720000,
                "taxes": 40000,
                "existing_debt_payment": 100000,
                "cash_balance": cash,
            }
        )
    forecast_request = ForecastRequest.model_validate(
        {
            "company_id": "demo_cafe",
            "industry": "cafe",
            "business_age_months": 36,
            "history": history,
            "horizon_months": 12,
        }
    )
    loan = LoanScenario(
        amount=3000000,
        term_months=36,
        annual_rate_percent=18,
        purpose="development",
        investment_amount=3000000,
        monthly_revenue_effect=100000,
        ramp_months=6,
    )
    quest = QuestRequest.model_validate(
        {
            "forecast_request": forecast_request.model_dump(mode="json"),
            "scoring": {
                "product_id": "business_loan",
                "requested_amount": 3000000,
                "term_months": 36,
                "business_age_months": 36,
                "monthly_revenue": history[-1]["revenue"],
                "net_margin_percent": 10,
                "debt_to_revenue_ratio": 1.5,
                "has_overdue_debt": False,
                "credit_history_score": 680,
                "has_collateral": False,
                "legal_form": "ip",
            },
            "loan": loan.model_dump(),
            "target_score": 70,
            "existing_debt_balance": 1500000,
            "minimum_acceptable_amount": 1500000,
        }
    )
    return forecast_request, loan, quest


def test_forecast_is_reproducible_and_does_not_assume_credit_growth() -> None:
    """Baseline строится только по истории и помечает интервалы как эвристику."""
    request, _, _ = _inputs()
    first = forecast_financials(request)
    assert first == forecast_financials(request)
    assert len(first.months) == 12
    assert first.months[0].revenue_low <= first.months[0].revenue <= first.months[0].revenue_high
    assert first.interval_type == "heuristic_not_calibrated"
    broken = request.model_dump(mode="json")
    broken["history"][1]["month"] = "2025-04-01"
    with pytest.raises(ValueError, match="последовательные месяцы"):
        ForecastRequest.model_validate(broken)


def test_loan_disbursement_is_not_profit_and_rate_changes_payment() -> None:
    """Кредит и инвестиция входят в деньги раздельно; ставка влияет на график."""
    request, loan, _ = _inputs()
    forecast = forecast_financials(request)
    no_credit = simulate_finances(SimulationRequest(forecast=forecast))
    with_credit = simulate_finances(SimulationRequest(forecast=forecast, loan=loan))
    cheaper = simulate_finances(
        SimulationRequest(forecast=forecast, loan=loan.model_copy(update={"annual_rate_percent": 8}))
    )
    first = with_credit.scenarios[0].months[0]
    assert first.loan_disbursement == first.investment_and_payoff == loan.amount
    assert first.revenue - no_credit.scenarios[0].months[0].revenue < loan.amount
    assert with_credit.monthly_payment > cheaper.monthly_payment
    assert with_credit == simulate_finances(SimulationRequest(forecast=forecast, loan=loan))
    assert with_credit.scenarios[2].minimum_cash < with_credit.scenarios[0].minimum_cash
    recovered = forecast.model_copy(update={"opening_cash": -1})
    recovered = recovered.model_copy(update={"months": [recovered.months[0]]})
    initial_gap = simulate_finances(SimulationRequest(forecast=recovered))
    assert initial_gap.scenarios[0].months[0].closing_cash > 0
    assert initial_gap.scenarios[0].minimum_cash == -1
    with pytest.raises(ValueError, match="эффект требует"):
        LoanScenario(
            amount=1000000,
            term_months=12,
            annual_rate_percent=12,
            purpose="development",
            monthly_revenue_effect=100000,
        )


def test_quest_recalculates_same_scoring_and_rejects_invented_actions() -> None:
    """Погашение долга тратит резерв, а возраст и кредитная история не меняются."""
    _, _, request = _inputs()
    scoring = ScoringEngine.from_json()
    response = generate_quest(request, scoring)
    assert response.plans
    assert response.plans[0].projected_score > response.baseline_score
    assert response.plans[0].requires_verification
    assert not response.plans[0].guarantees_approval
    selected = response.plans[0].actions
    recalculated = recalculate_quest(
        RecalculateRequest.model_validate(
            {**request.model_dump(mode="json"), "actions": [x.model_dump() for x in selected]}
        ),
        scoring,
    )
    assert recalculated.plan == response.plans[0]
    if any(action.type == "repay_existing_debt" for action in selected):
        assert recalculated.forecast.opening_cash < request.forecast_request.history[-1].cash_balance
    altered = [x.model_dump() for x in selected]
    altered[0]["to_value"] = 1
    with pytest.raises(ValueError, match="не входит в допустимые"):
        recalculate_quest(
            RecalculateRequest.model_validate({**request.model_dump(mode="json"), "actions": altered}), scoring
        )


def test_four_routes_work_together_without_paid_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Реальный HTTP-контракт проходит на подменном LLM и локальных формулах."""
    monkeypatch.setattr("app.main.create_assistant", lambda settings: FakeAssistant())
    history, loan, quest = _inputs()
    with TestClient(create_app(llm_client=FakeLlm(), ocr_client=FakeOcr())) as client:
        forecast = client.post("/ml/forecast", json=history.model_dump(mode="json"))
        assert forecast.status_code == 200
        simulation = client.post(
            "/ml/simulate", json={"forecast": forecast.json(), "loan": loan.model_dump(mode="json")}
        )
        assert simulation.status_code == 200
        generated = client.post("/ml/quest/generate", json=quest.model_dump(mode="json"))
        assert generated.status_code == 200
        selected = generated.json()["plans"][0]["actions"]
        recalculated = client.post("/ml/quest/recalculate", json={**quest.model_dump(mode="json"), "actions": selected})
        assert recalculated.status_code == 200
        assert recalculated.json()["plan"] == generated.json()["plans"][0]
        assert client.get("/financial-intelligence").status_code == 404
        assert client.get("/ml/demo/risky").json()["forecast_request"]["company_id"] == "demo_risky"
        assert client.get("/ml/demo/unknown").status_code == 422
        paths = client.get("/openapi.json").json()["paths"]
        assert all(
            path in paths for path in ("/ml/forecast", "/ml/simulate", "/ml/quest/generate", "/ml/quest/recalculate")
        )
        assert (
            client.post("/ml/forecast", json={**history.model_dump(mode="json"), "company_id": "real_123"}).status_code
            == 422
        )


def test_demo_profiles_have_distinct_risk_and_cash_outcomes() -> None:
    """Синтетические профили различаются по баллу и денежной устойчивости."""
    scoring = ScoringEngine.from_json()
    stable = demo_case("stable")
    seasonal = demo_case("seasonal")
    risky = demo_case("risky")
    stable_quest = generate_quest(stable, scoring)
    seasonal_quest = generate_quest(seasonal, scoring)
    risky_quest = generate_quest(risky, scoring)
    assert {item.scoring.legal_form for item in (stable, seasonal, risky)} == {"ip", "ooo"}
    assert stable_quest.baseline_score > seasonal_quest.baseline_score > risky_quest.baseline_score
    assert not stable_quest.plans
    assert risky_quest.plans
    assert all(not plan.target_reached for plan in risky_quest.plans)
    stable_cash = simulate_finances(SimulationRequest(forecast=forecast_financials(stable.forecast_request)))
    risky_cash = simulate_finances(SimulationRequest(forecast=forecast_financials(risky.forecast_request)))
    assert stable_cash.scenarios[0].minimum_cash > risky_cash.scenarios[0].minimum_cash
    assert all(not hasattr(result, "cash_gap_probability") for result in (stable_cash, risky_cash))
    for profile in (stable, seasonal, risky):
        evaluation = rolling_backtest(profile.forecast_request)
        assert 0 <= evaluation["revenue_wape"] < 0.1
        assert 0 <= evaluation["interval_coverage"] <= 1
