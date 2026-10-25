"""Оценка сложности и приоритета, проверка объяснения OpenRouter."""

from __future__ import annotations

from typing import Literal

from pydantic import ValidationError

from app.llm import ChatCompletionClient, LlmResponseError
from app.llm_json import json_payload
from underwriting.config import CONFIG, UnderwritingConfig
from underwriting.prompts import ASSESSMENT_RESPONSE_FORMAT, SYSTEM_PROMPT, assessment_prompt
from underwriting.schema import (
    Classification,
    Finding,
    GeneratedAssessment,
    OverallAssessment,
    PriorityClassification,
    UnderwritingRequest,
    UnderwritingResponse,
)


def analyze_case(
    snapshot: UnderwritingRequest, llm: ChatCompletionClient, config: UnderwritingConfig = CONFIG
) -> UnderwritingResponse:
    """Использует готовый скоринг, классифицирует кейс и запрашивает текст у LLM.

    Args:
        snapshot: Проверенный снимок заявки.
        llm: Клиент языковой модели.
        config: Типизированные настройки сервиса.

    Returns:
        UnderwritingResponse: Резюме с выводами, сложностью и приоритетом.

    Raises:
        LlmResponseError: Ответ LLM нарушает формат или ссылается на неподтверждённые данные.
    """
    paths = evidence_paths(snapshot)
    completion = llm.complete(
        SYSTEM_PROMPT,
        assessment_prompt(snapshot, paths),
        config.max_output_tokens,
        response_format=ASSESSMENT_RESPONSE_FORMAT,
    )
    try:
        generated = GeneratedAssessment.model_validate_json(json_payload(completion.content))
    except ValidationError as error:
        raise LlmResponseError("OpenRouter вернул неверный формат резюме заявки.") from error
    findings = generated.strengths + generated.risks + generated.missing_data + generated.next_actions
    if any(path not in paths for path in generated.evidence):
        raise LlmResponseError("OpenRouter сослался на поле вне снимка заявки.")
    for item in findings:
        if any(path not in paths for path in item.evidence):
            raise LlmResponseError("OpenRouter сослался на поле вне снимка заявки.")
    actions = generated.next_actions
    if not actions:
        for check in snapshot.checks:
            if check.status == "missing":
                actions = [
                    Finding(
                        text=f"Запросить недостающие сведения: {check.label}.",
                        evidence=[f"checks.{check.check_id}.status"],
                    )
                ]
                break
            if check.status == "flag":
                actions = [
                    Finding(
                        text=f"Уточнить причину сигнала проверки: {check.label}.",
                        evidence=[f"checks.{check.check_id}.status"],
                    )
                ]
                break
    return UnderwritingResponse(
        case_id=snapshot.case_id,
        overall_assessment=OverallAssessment(
            level=_overall_level(snapshot, config), summary=generated.summary, evidence=generated.evidence
        ),
        strengths=generated.strengths,
        risks=generated.risks,
        missing_data=generated.missing_data,
        next_actions=actions,
        decision_complexity=decision_complexity(snapshot, config),
        analyst_priority=analyst_priority(snapshot, config),
        scoring_model_version=snapshot.scoring.model_version,
        model=completion.model,
    )


def evidence_paths(snapshot: UnderwritingRequest) -> set[str]:
    """Строит ссылки на реальные поля переданного снимка, включая доп. факты.

    Args:
        snapshot: Проверенный снимок заявки.

    Returns:
        set[str]: Множество допустимых путей к полям.
    """
    paths: set[str] = set()
    for section in ("business", "application", "financials", "scoring"):
        for key, value in getattr(snapshot, section).model_dump().items():
            if isinstance(value, list):
                paths.update(f"{section}.{key}[{index}].{field}" for index, item in enumerate(value) for field in item)
            else:
                paths.add(f"{section}.{key}")
    for check in snapshot.checks:
        paths.update(f"checks.{check.check_id}.{field}" for field in ("label", "status", "details", "source"))
    for fact in snapshot.additional_facts:
        paths.update(f"additional_facts.{fact.fact_id}.{field}" for field in ("value", "source"))
    return paths


def decision_complexity(snapshot: UnderwritingRequest, config: UnderwritingConfig = CONFIG) -> Classification:
    """Оценивает объём ручной проверки, а не трудность клиента для банка.

    Args:
        snapshot: Проверенный снимок заявки.
        config: Типизированные настройки сервиса.

    Returns:
        Classification: Уровень сложности ручной проверки.
    """
    issues = [check for check in snapshot.checks if check.status != "clear"]
    risk = snapshot.scoring.risk_probability
    evidence = [f"checks.{check.check_id}.status" for check in issues]
    if not snapshot.checks:
        return Classification(level="high", reason="Результаты проверок отсутствуют.", evidence=[])
    if len(issues) >= config.high_complexity_issue_count or risk >= config.high_risk_probability:
        return Classification(
            level="high",
            reason="Нужна расширенная ручная проверка из-за сигналов проверок или высокого скорингового риска.",
            evidence=evidence or ["scoring.risk_probability"],
        )
    if issues or risk >= config.medium_risk_probability:
        return Classification(
            level="medium",
            reason="Есть отдельные вопросы для проверки аналитиком.",
            evidence=evidence or ["scoring.risk_probability"],
        )
    return Classification(
        level="low", reason="По переданным данным дополнительных сигналов мало.", evidence=["scoring.risk_probability"]
    )


def analyst_priority(snapshot: UnderwritingRequest, config: UnderwritingConfig = CONFIG) -> PriorityClassification:
    """Ставит приоритет внимания по сумме относительно масштаба бизнеса и риску.

    Args:
        snapshot: Проверенный снимок заявки.
        config: Типизированные настройки сервиса.

    Returns:
        PriorityClassification: Приоритет заявки для аналитика.
    """
    segment = snapshot.business.segment
    revenue = snapshot.financials.monthly_revenue
    exposure = snapshot.application.requested_amount / revenue if revenue else None
    medium = config.micro_medium_exposure_months if segment == "micro" else config.small_medium_exposure_months
    high = config.micro_high_exposure_months if segment == "micro" else config.small_high_exposure_months
    evidence = ["business.segment", "application.requested_amount", "financials.monthly_revenue"]
    if exposure is None:
        return PriorityClassification(
            level="high",
            reason="Нет месячной выручки для оценки размера кредита относительно бизнеса.",
            evidence=evidence,
            exposure_months=None,
            business_segment=segment,
        )
    risk = snapshot.scoring.risk_probability
    if exposure >= high or (exposure >= medium and risk >= config.high_risk_probability):
        level: Literal["low", "medium", "high"] = "high"
    elif exposure >= medium or risk >= config.medium_risk_probability:
        level = "medium"
    else:
        level = "low"
    if risk >= config.medium_risk_probability:
        evidence.append("scoring.risk_probability")
    return PriorityClassification(
        level=level,
        reason="Приоритет внимания рассчитан по сумме кредита относительно месячной выручки и скоринговому риску.",
        evidence=evidence,
        exposure_months=round(exposure, 2),
        business_segment=segment,
    )


def _overall_level(
    snapshot: UnderwritingRequest, config: UnderwritingConfig
) -> Literal["positive", "mixed", "concerning", "insufficient_data"]:
    """Определяет общую оценку заявки по рискам и проверкам.

    Args:
        snapshot: Проверенный снимок заявки.
        config: Типизированные настройки сервиса.

    Returns:
        Literal['positive', 'mixed', 'concerning', 'insufficient_data']: Категория общей оценки заявки.
    """
    if not snapshot.checks or any(item.status == "missing" for item in snapshot.checks):
        return "insufficient_data"
    if snapshot.scoring.risk_probability >= config.high_risk_probability or any(
        item.status == "flag" for item in snapshot.checks
    ):
        return "concerning"
    if snapshot.scoring.risk_probability >= config.medium_risk_probability:
        return "mixed"
    return "positive"
