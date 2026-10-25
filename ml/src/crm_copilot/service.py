"""Проверяет источники ответа и обязательные поля перед показом черновика."""

from __future__ import annotations

from pydantic import ValidationError

from app.llm import ChatCompletionClient, LlmResponseError
from app.llm_json import json_payload
from crm_copilot.config import CONFIG, CopilotConfig
from crm_copilot.prompts import RESPONSE_FORMAT, SYSTEM_PROMPT, copilot_prompt
from crm_copilot.schema import CopilotRequest, CopilotResponse, GeneratedCopilot, MissingDatum, NextAction


def prepare_reply(
    request: CopilotRequest, llm: ChatCompletionClient, config: CopilotConfig = CONFIG
) -> CopilotResponse:
    """Готовит черновик; при пробелах запрещает окончательный ответ.

    Args:
        request: Проверенные входные данные.
        llm: Клиент языковой модели.
        config: Типизированные настройки сервиса.

    Returns:
        CopilotResponse: Черновик ответа и список недостающих сведений.

    Raises:
        LlmResponseError: Ответ LLM нарушает формат или ссылается на неподтверждённые данные.
    """
    evidence = evidence_values(request)
    completion = llm.complete(
        SYSTEM_PROMPT,
        copilot_prompt(request, set(evidence)),
        config.max_output_tokens,
        response_format=RESPONSE_FORMAT,
    )
    try:
        generated = GeneratedCopilot.model_validate_json(json_payload(completion.content))
    except ValidationError as error:
        raise LlmResponseError("OpenRouter вернул неверный формат CRM-ответа.") from error
    missing: dict[str, MissingDatum] = {item.path: item for item in generated.missing_data}
    for required in request.required_fields:
        value = evidence.get(required.path)
        if value is None or (required.acceptable_values and str(value) not in required.acceptable_values):
            missing[required.path] = MissingDatum(
                path=required.path,
                label=required.label,
                reason=required.reason,
                obtain_from=required.obtain_from,
            )
    if not any(
        path.startswith(
            ("application.", "profile.", "scoring.", "checks.", "documents.", "underwriting.", "verified_facts.")
        )
        for path in evidence
    ):
        missing["case_context"] = MissingDatum(
            path="case_context",
            label="Данные обращения и заявки",
            reason="Без контекста нельзя проверить состояние обращения и подготовить ответ.",
            obtain_from="backend",
        )
    missing_data = list(missing.values())
    required_sources = {
        field.path: f"required_fields[{index}].path"
        for index, field in enumerate(request.required_fields)
        if field.path not in evidence
    }
    summary_evidence = [required_sources.get(path, path) for path in generated.summary_evidence]
    generated_actions = [
        NextAction(text=action.text, evidence=[required_sources.get(path, path) for path in action.evidence])
        for action in generated.next_actions
    ]
    referenced = list(summary_evidence)
    if not missing_data:
        referenced += [path for action in generated_actions for path in action.evidence]
        referenced += generated.reply_evidence
    unknown = [path for path in referenced if path not in evidence]
    if unknown:
        raise LlmResponseError(f"OpenRouter сослался на данные вне снимка CRM: {', '.join(unknown)}.")
    if not missing_data and any(
        path.startswith(("history.", "required_fields[")) or path == "customer_question"
        for path in generated.reply_evidence
    ):
        raise LlmResponseError("Сообщение клиента нельзя использовать как подтверждённый факт в ответе.")
    if missing_data:
        actions = [_missing_action(item, required_sources.get(item.path)) for item in missing_data]
        reply_draft = _clarification_draft(missing_data)
        reply_evidence: list[str] = []
    else:
        actions = generated_actions
        if not generated.reply_evidence:
            raise LlmResponseError("Для готового ответа нет ссылок на подтверждённые данные.")
        reply_draft = generated.reply_draft
        reply_evidence = generated.reply_evidence
    return CopilotResponse(
        case_id=request.case_id,
        answerability="needs_data" if missing_data else "ready",
        summary=generated.summary,
        summary_evidence=summary_evidence,
        missing_data=missing_data,
        next_actions=actions,
        reply_draft=reply_draft,
        reply_evidence=reply_evidence,
        model=completion.model,
    )


def _missing_action(item: MissingDatum, evidence: str | None) -> NextAction:
    """Создаёт действие для получения недостающих данных.

    Args:
        item: Обрабатываемый элемент.
        evidence: Пути к подтверждающим полям.

    Returns:
        NextAction: Действие по получению недостающих данных.
    """
    verbs = {
        "customer": "Запросить у клиента",
        "employee": "Уточнить у сотрудника",
        "backend": "Получить из CRM",
        "document": "Проверить документ",
        "check": "Завершить проверку",
    }
    return NextAction(text=f"{verbs[item.obtain_from]}: {item.label}.", evidence=[evidence] if evidence else [])


def _clarification_draft(missing_data: list[MissingDatum]) -> str:
    """Составляет черновик запроса недостающих данных.

    Args:
        missing_data: Недостающие сведения.

    Returns:
        str: Сформированный текст.
    """
    customer = [item.label.lower() for item in missing_data if item.obtain_from == "customer"]
    internal = [item.label.lower() for item in missing_data if item.obtain_from != "customer"]
    parts = []
    if customer:
        parts.append(f"Чтобы ответить на ваш вопрос, пожалуйста, уточните: {', '.join(customer[:3])}.")
    if internal:
        parts.append(f"Мы уточняем {', '.join(internal[:3])} и вернёмся с ответом после проверки.")
    return " ".join(parts)


def evidence_values(request: CopilotRequest) -> dict[str, object]:
    """Пути к реально присутствующим скалярным полям, которые можно цитировать.

    Args:
        request: Проверенные входные данные.

    Returns:
        dict[str, object]: Структурированные данные для API или LLM.
    """
    values: dict[str, object] = {}
    values["customer_question"] = request.customer_question
    for section in ("application", "profile", "scoring", "underwriting"):
        data = getattr(request, section)
        if data is not None:
            _add_scalars(values, section, data.model_dump())
    for message in request.history:
        values[f"history.{message.message_id}.text"] = message.text
    for index, required in enumerate(request.required_fields):
        _add_scalars(values, f"required_fields[{index}]", required.model_dump())
    for collection, id_field in (
        ("checks", "check_id"),
        ("documents", "document_id"),
        ("verified_facts", "fact_id"),
    ):
        for item in getattr(request, collection):
            _add_scalars(values, f"{collection}.{getattr(item, id_field)}", item.model_dump())
    return values


def _add_scalars(values: dict[str, object], prefix: str, data: object) -> None:
    """Добавляет скалярные значения и их пути.

    Args:
        values: Значения.
        prefix: Префикс.
        data: Данные.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            _add_scalars(values, f"{prefix}.{key}", value)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            _add_scalars(values, f"{prefix}[{index}]", value)
    elif data is not None and data != "":
        values[prefix] = data
