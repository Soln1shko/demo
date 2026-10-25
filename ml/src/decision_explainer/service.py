"""Перевод рисков уже отклонённой сотрудником заявки на понятный язык."""

from __future__ import annotations

from pydantic import ValidationError

from app.llm import ChatCompletionClient, LlmResponseError
from app.llm_json import json_payload
from decision_explainer.config import CONFIG, ExplanationConfig
from decision_explainer.prompts import RESPONSE_FORMAT, SYSTEM_PROMPT, explanation_prompt
from decision_explainer.schema import GeneratedExplanation, RefusalExplanationRequest, RefusalExplanationResponse

FACTOR_LABELS = {
    "requested_amount": "размер запрошенной суммы",
    "business_age_months": "срок работы бизнеса",
    "monthly_revenue": "месячная выручка",
    "net_margin_percent": "чистая маржа",
    "debt_to_revenue_ratio": "долговая нагрузка относительно выручки",
    "credit_history_score": "оценка кредитной истории",
    "has_overdue_debt": "просроченная задолженность",
}


def explain_refusal(
    request: RefusalExplanationRequest, llm: ChatCompletionClient, config: ExplanationConfig = CONFIG
) -> RefusalExplanationResponse:
    """Формирует одно сообщение; причиной служат риски показанного сотруднику резюме.

    Args:
        request: Проверенные входные данные.
        llm: Клиент языковой модели.
        config: Типизированные настройки сервиса.

    Returns:
        RefusalExplanationResponse: Сообщение с причиной отказа.

    Raises:
        ValueError: Входные данные нарушают ограничения домена.
        LlmResponseError: Ответ LLM нарушает формат или ссылается на неподтверждённые данные.
    """
    risks = request.underwriting.risks
    if not risks:
        raise ValueError("В резюме нет рисков, на которых можно обосновать отказ.")
    scoring_factors: list[str] = []
    risk_evidence = {path for risk in risks for path in risk.evidence}
    if request.scoring:
        scoring_factors = [
            FACTOR_LABELS[factor.feature]
            for factor in sorted(request.scoring.factors, key=lambda item: item.contribution, reverse=True)
            if factor.contribution > 0
            and factor.feature in FACTOR_LABELS
            and (
                f"financials.{factor.feature}" in risk_evidence
                or f"business.{factor.feature}" in risk_evidence
                or f"application.{factor.feature}" in risk_evidence
                or "scoring.risk_probability" in risk_evidence
                or "scoring.risk_band" in risk_evidence
            )
        ][: config.max_scoring_factors]
    completion = llm.complete(
        SYSTEM_PROMPT,
        explanation_prompt([{"index": index, "text": risk.text} for index, risk in enumerate(risks)], scoring_factors),
        config.max_output_tokens,
        response_format=RESPONSE_FORMAT,
    )
    try:
        generated = GeneratedExplanation.model_validate_json(json_payload(completion.content))
    except ValidationError as error:
        raise LlmResponseError("OpenRouter вернул неверный формат объяснения отказа.") from error
    if len(set(generated.risk_indexes)) != len(generated.risk_indexes) or any(
        index < 0 or index >= len(risks) for index in generated.risk_indexes
    ):
        raise LlmResponseError("OpenRouter сослался на риск вне резюме заявки.")
    return RefusalExplanationResponse(message=generated.message.strip())
