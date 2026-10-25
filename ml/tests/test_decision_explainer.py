"""Проверки объяснения ручного отказа по готовому резюме."""

import json

import pytest
from pydantic import ValidationError

from app.llm import LlmCompletion, LlmResponseError
from decision_explainer.schema import RefusalExplanationRequest
from decision_explainer.service import explain_refusal


class CapturingLlm:
    def __init__(self, risk_indexes: list[int] | None = None) -> None:
        self.risk_indexes = [0] if risk_indexes is None else risk_indexes
        self.prompt = ""

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int, response_format: dict[str, object] | None = None
    ) -> LlmCompletion:
        del system_prompt, max_tokens
        assert response_format is not None
        self.prompt = user_prompt
        return LlmCompletion(
            content=json.dumps(
                {"message": "В заявке указана высокая долговая нагрузка.", "risk_indexes": self.risk_indexes},
                ensure_ascii=False,
            ),
            model="fake/openrouter",
            input_tokens=1,
            output_tokens=1,
        )


def refusal_payload() -> dict[str, object]:
    return {
        "decision": "declined",
        "underwriting": {
            "case_id": "DEMO-001",
            "overall_assessment": {
                "level": "concerning",
                "summary": "Долговая нагрузка требует проверки.",
                "evidence": ["financials.debt_to_revenue_ratio"],
            },
            "strengths": [],
            "risks": [{"text": "Высокая долговая нагрузка.", "evidence": ["financials.debt_to_revenue_ratio"]}],
            "missing_data": [],
            "next_actions": [],
            "decision_complexity": {"level": "high", "reason": "Нужна ручная проверка.", "evidence": []},
            "analyst_priority": {
                "level": "high",
                "reason": "Высокий риск.",
                "evidence": [],
                "exposure_months": 2.5,
                "business_segment": "micro",
            },
            "scoring_model_version": "demo-v1",
            "model": "fake/openrouter",
            "synthetic": True,
        },
        "scoring": {
            "risk_probability": 0.72,
            "risk_band": "high",
            "model_version": "demo-v1",
            "factors": [
                {"feature": "debt_to_revenue_ratio", "contribution": 0.8},
                {"feature": "monthly_revenue", "contribution": -0.2},
            ],
        },
    }


def test_only_relevant_risk_factors_reach_llm() -> None:
    llm = CapturingLlm()
    result = explain_refusal(RefusalExplanationRequest.model_validate(refusal_payload()), llm)
    sent = json.loads(llm.prompt)
    assert result.model_dump() == {"message": "В заявке указана высокая долговая нагрузка."}
    assert sent["risks"] == [{"index": 0, "text": "Высокая долговая нагрузка."}]
    assert sent["scoring_factors_increasing_risk"] == ["долговая нагрузка относительно выручки"]


def test_refusal_requires_risk_and_matching_scoring_version() -> None:
    payload = refusal_payload()
    payload["underwriting"]["risks"] = []  # type: ignore[index]
    with pytest.raises(ValueError, match="нет рисков"):
        explain_refusal(RefusalExplanationRequest.model_validate(payload), CapturingLlm())

    payload = refusal_payload()
    payload["scoring"]["model_version"] = "another-version"  # type: ignore[index]
    with pytest.raises(ValidationError, match="Версия скоринга"):
        RefusalExplanationRequest.model_validate(payload)


def test_llm_cannot_cite_unknown_risk() -> None:
    with pytest.raises(LlmResponseError, match="вне резюме"):
        explain_refusal(RefusalExplanationRequest.model_validate(refusal_payload()), CapturingLlm([1]))
