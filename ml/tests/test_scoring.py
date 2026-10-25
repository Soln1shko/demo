"""Проверки воспроизводимости и мгновенного локального inference."""

from dataclasses import replace

from scoring import ScoringEngine, ScoringInput


def _request(amount: int) -> ScoringInput:
    return ScoringInput(
        product_id="business_loan",
        requested_amount=amount,
        term_months=36,
        business_age_months=28,
        monthly_revenue=1_500_000,
        net_margin_percent=18,
        debt_to_revenue_ratio=0.8,
        has_overdue_debt=False,
        credit_history_score=720,
        has_collateral=False,
        legal_form="ip",
    )


def test_higher_amount_increases_risk_for_same_profile() -> None:
    engine = ScoringEngine.from_json()
    assert engine.score(_request(3_000_000)).risk_probability > engine.score(_request(500_000)).risk_probability


def test_browser_payload_contains_all_data_for_local_calculation() -> None:
    payload = ScoringEngine.from_json().browser_payload()
    assert payload["numeric_weights"]
    assert payload["categorical_weights"]


def test_distressed_business_has_much_higher_risk_than_healthy_business() -> None:
    """Плохая кредитная история и нагрузка меняют оценку, а не только сумму."""
    engine = ScoringEngine.from_json()
    healthy = _request(2_000_000)
    distressed = replace(
        healthy,
        business_age_months=3,
        monthly_revenue=200000,
        net_margin_percent=3,
        debt_to_revenue_ratio=4,
        has_overdue_debt=True,
        credit_history_score=300,
    )
    healthy_result = engine.score(healthy)
    distressed_result = engine.score(distressed)
    assert healthy_result.risk_probability < 0.35
    assert distressed_result.risk_probability > 0.65
    assert distressed_result.risk_probability > healthy_result.risk_probability
    assert distressed_result.risk_band == "высокий"
    assert any(factor.contribution > 0 for factor in distressed_result.factors)
