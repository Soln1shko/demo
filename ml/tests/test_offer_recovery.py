"""Локальный перебор кредитных условий без LLM и HTTP-запросов."""

from copy import deepcopy

from offer_recovery.schema import RecoveryRequest
from offer_recovery.service import recover_offers
from scoring import ScoringEngine


def test_recovery_uses_existing_weights_and_product_limits() -> None:
    request = RecoveryRequest.model_validate(
        {
            "case_id": "DEMO-RECOVERY-1",
            "profile": {
                "requested_amount": 2000000,
                "term_months": 36,
                "purpose": "working_capital",
                "business_age_months": 24,
                "monthly_revenue": 900000,
                "net_margin_percent": 12,
                "debt_to_revenue_ratio": 0.8,
                "has_overdue_debt": False,
                "credit_history_score": 700,
                "has_collateral": False,
                "legal_form": "ip",
                "has_marketplace_sales": False,
                "has_existing_business_loans": False,
            },
            "declined_offers": [
                {
                    "product_id": "business_loan",
                    "requested_amount": 2000000,
                    "term_months": 36,
                    "reasons": ["Высокая долговая нагрузка."],
                }
            ],
            "recommended_product_ids": ["business_loan", "business_pledge_loan"],
            "minimum_acceptable_amount": 800000,
            "minimum_acceptable_term_months": 12,
        }
    )
    result = recover_offers(request, ScoringEngine.from_json())
    assert result.variants
    assert all(item.suggested_terms.amount >= 800000 for item in result.variants)
    assert all(item.risk_change_vs_original < 0 for item in result.variants)
    assert all(item.model_version == "synthetic-logreg-1" for item in result.variants)
    assert all(item.product_id != "business_pledge_loan" for item in result.variants)
    assert result.unavailable_products[0].product_id == "business_pledge_loan"
    assert result.declined_reasons == ["Высокая долговая нагрузка."]
    assert result.estimate_type == "synthetic_risk_probability"


def test_recovery_never_repeats_declined_terms_or_exceeds_customer_limits() -> None:
    """Альтернативы действительно меняют условия и снижают модельный риск."""
    payload = {
        "case_id": "DEMO-RECOVERY-2",
        "profile": {
            "requested_amount": 2000000,
            "term_months": 36,
            "purpose": "working_capital",
            "business_age_months": 24,
            "monthly_revenue": 900000,
            "net_margin_percent": 12,
            "debt_to_revenue_ratio": 0.8,
            "has_overdue_debt": False,
            "credit_history_score": 700,
            "has_collateral": False,
            "legal_form": "ip",
            "has_marketplace_sales": False,
            "has_existing_business_loans": False,
        },
        "declined_offers": [
            {
                "product_id": "business_loan",
                "requested_amount": 2000000,
                "term_months": 36,
                "reasons": ["Высокая долговая нагрузка."],
            }
        ],
        "recommended_product_ids": ["business_loan", "credit_line"],
        "minimum_acceptable_amount": 800000,
        "minimum_acceptable_term_months": 12,
    }
    result = recover_offers(RecoveryRequest.model_validate(payload), ScoringEngine.from_json())
    assert result.variants
    for variant in result.variants:
        assert (variant.product_id, variant.suggested_terms.amount, variant.suggested_terms.term_months) != (
            "business_loan",
            2000000,
            36,
        )
        assert 800000 <= variant.suggested_terms.amount <= 2000000
        assert 12 <= variant.suggested_terms.term_months <= 36
        assert variant.risk_change_vs_original <= -0.01

    impossible = deepcopy(payload)
    impossible["minimum_acceptable_amount"] = 2000000
    impossible["minimum_acceptable_term_months"] = 36
    unavailable = recover_offers(RecoveryRequest.model_validate(impossible), ScoringEngine.from_json())
    assert all(item.product_id != "business_loan" for item in unavailable.variants)
