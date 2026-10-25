"""Проверяет выбор кредитных продуктов и связку с scoring engine."""

from dataclasses import replace

from credit_advisor import CreditAdvisor, CreditAdvisorInput


def _request(**changes: object) -> CreditAdvisorInput:
    values: dict[str, object] = {
        "requested_amount": 800000,
        "term_months": 12,
        "purpose": "working_capital",
        "business_age_months": 16,
        "monthly_revenue": 1500000,
        "net_margin_percent": 18,
        "debt_to_revenue_ratio": 0.6,
        "has_overdue_debt": False,
        "credit_history_score": 720,
        "has_collateral": False,
        "legal_form": "ip",
        "has_marketplace_sales": False,
        "has_existing_business_loans": False,
    }
    values.update(changes)
    return CreditAdvisorInput(**values)


def test_advisor_returns_only_eligible_credit_product_ids() -> None:
    advice = CreditAdvisor.default().recommend(_request(), top_n=3)
    assert len(advice.recommendations) == 3
    assert {item.product_id for item in advice.recommendations} <= {"business_loan", "credit_line", "alfa_start"}
    assert "seller_credit" in advice.excluded_product_ids


def test_seller_credit_is_recommended_only_for_marketplace_seller() -> None:
    advice = CreditAdvisor.default().recommend(
        _request(
            requested_amount=500000,
            term_months=6,
            has_marketplace_sales=True,
            context_tags=("marketplace", "inventory"),
        ),
        top_n=5,
    )
    assert "seller_credit" in {item.product_id for item in advice.recommendations}


def test_context_and_approval_probability_form_combined_rank() -> None:
    advice = CreditAdvisor.default().recommend(
        _request(
            requested_amount=500000,
            term_months=6,
            has_marketplace_sales=True,
            context_tags=("marketplace", "inventory"),
        ),
        top_n=1,
    )
    recommendation = advice.recommendations[0]
    assert recommendation.product_id == "seller_credit"
    assert recommendation.combined_score > recommendation.preliminary_approval_probability * 0.6
    assert recommendation.context_relevance > 0


def test_llm_context_cannot_contain_unchecked_product_id() -> None:
    advice = CreditAdvisor.default().recommend(_request(), top_n=2)
    context_ids = {item["product_id"] for item in advice.llm_context()["recommendations"]}
    recommendation_ids = {item.product_id for item in advice.recommendations}
    assert context_ids == recommendation_ids


def test_business_purpose_changes_first_credit_product() -> None:
    """Продукт в топе соответствует цели и условиям конкретной заявки."""
    advisor = CreditAdvisor.default()
    base = _request()
    scenarios = (
        (replace(base, purpose="cash_gap", term_months=6), "overdraft"),
        (
            replace(
                base, purpose="inventory", term_months=6, has_marketplace_sales=True, context_tags=("marketplace",)
            ),
            "seller_credit",
        ),
        (replace(base, purpose="refinancing", has_existing_business_loans=True), "business_refinancing"),
        (
            replace(
                base,
                purpose="commercial_property_purchase",
                has_collateral=True,
                requested_amount=10000000,
                term_months=60,
            ),
            "business_mortgage",
        ),
    )
    for profile, expected_product in scenarios:
        advice = advisor.recommend(profile)
        assert advice.recommendations[0].product_id == expected_product
        assert advice.recommendations[0].context_relevance > 0


def test_weak_business_has_low_preliminary_approval_probability() -> None:
    """Кредитный советник использует риск того же скоринга без инверсии смысла."""
    advisor = CreditAdvisor.default()
    healthy = advisor.recommend(_request()).recommendations[0]
    weak = advisor.recommend(
        _request(
            business_age_months=3,
            monthly_revenue=200000,
            net_margin_percent=3,
            debt_to_revenue_ratio=4,
            has_overdue_debt=True,
            credit_history_score=300,
        )
    ).recommendations[0]
    assert weak.preliminary_approval_probability < 0.1
    assert weak.preliminary_approval_probability < healthy.preliminary_approval_probability
    assert weak.risk_probability > healthy.risk_probability
