"""Проверка приоритета по масштабу и границы данных для OpenRouter."""

import json

import pytest

from app.llm import LlmCompletion, LlmResponseError
from underwriting.schema import UnderwritingRequest
from underwriting.service import analyst_priority, analyze_case, decision_complexity, evidence_paths


def demo_case() -> dict[str, object]:
    """Фиксированный синтетический снимок для проверок андеррайтинга."""
    return {
        "case_id": "DEMO-UNDERWRITING-1",
        "business": {"segment": "micro", "legal_form": "ip", "business_age_months": 48, "industry": "торговля"},
        "application": {
            "product_id": "business_loan",
            "requested_amount": 2000000,
            "term_months": 36,
            "purpose": "оборотные средства",
        },
        "financials": {"monthly_revenue": 800000, "net_margin_percent": 12, "debt_to_revenue_ratio": 0.8},
        "scoring": {"risk_probability": 0.72, "risk_band": "high", "factors": [], "model_version": "demo-backend-v1"},
        "checks": [
            {
                "check_id": "tax_status",
                "label": "Налоговый статус",
                "status": "clear",
                "details": "Нет сигналов",
                "source": "demo_tax",
            },
            {
                "check_id": "obligations",
                "label": "Действующие обязательства",
                "status": "missing",
                "details": "Нет данных",
                "source": "demo_bank",
            },
        ],
        "additional_facts": [{"fact_id": "sales_channel", "value": "маркетплейсы", "source": "demo_backend"}],
    }


class CapturingLlm:
    def __init__(self, evidence: str = "financials.debt_to_revenue_ratio") -> None:
        self.evidence = evidence
        self.prompt = ""

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int, response_format: dict[str, object] | None = None
    ) -> LlmCompletion:
        del system_prompt, max_tokens
        assert response_format is not None
        self.prompt = user_prompt
        answer = {
            "summary": "Долговая нагрузка требует внимания.",
            "evidence": [self.evidence],
            "strengths": [],
            "risks": [{"text": "Долговая нагрузка высокая.", "evidence": [self.evidence]}],
            "missing_data": [],
            "next_actions": [],
        }
        return LlmCompletion(
            content=json.dumps(answer, ensure_ascii=False), model="fake/openrouter", input_tokens=1, output_tokens=1
        )

    def close(self) -> None:
        pass


def test_micro_and_small_business_have_different_relative_priority() -> None:
    payload = demo_case()
    payload["application"]["requested_amount"] = 1600000  # type: ignore[index]
    payload["financials"]["monthly_revenue"] = 800000  # type: ignore[index]
    payload["scoring"]["risk_probability"] = 0.2  # type: ignore[index]
    micro = UnderwritingRequest.model_validate(payload)
    assert analyst_priority(micro).level == "high"
    payload["business"]["segment"] = "small"  # type: ignore[index]
    small = UnderwritingRequest.model_validate(payload)
    assert analyst_priority(small).level == "medium"
    assert analyst_priority(small).exposure_months == 2.0


def test_supplied_scoring_and_checks_reach_openrouter_without_recalculation() -> None:
    snapshot = UnderwritingRequest.model_validate(demo_case())
    llm = CapturingLlm()
    response = analyze_case(snapshot, llm)
    sent = json.loads(llm.prompt.split("case_snapshot:\n", 1)[1].split("\nallowed_evidence_paths:", 1)[0])
    assert sent["scoring"]["risk_probability"] == 0.72
    assert sent["checks"][1]["status"] == "missing"
    assert sent["additional_facts"][0]["value"] == "маркетплейсы"
    assert response.scoring_model_version == "demo-backend-v1"
    assert response.decision_complexity.level == "high"
    assert response.overall_assessment.level == "insufficient_data"
    assert response.next_actions[0].text == "Запросить недостающие сведения: Действующие обязательства."
    assert "checks.obligations.status" in evidence_paths(snapshot)


def test_unknown_evidence_is_rejected() -> None:
    snapshot = UnderwritingRequest.model_validate(demo_case())
    with pytest.raises(LlmResponseError, match="вне снимка"):
        analyze_case(snapshot, CapturingLlm("scoring.approval_decision"))


def test_missing_all_checks_requires_manual_review() -> None:
    payload = demo_case()
    payload["checks"] = []
    snapshot = UnderwritingRequest.model_validate(payload)
    assert decision_complexity(snapshot).level == "high"
