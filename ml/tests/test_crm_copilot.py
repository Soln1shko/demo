"""Пробелы в данных и ссылки CRM Copilot."""

import json

import pytest

from app.llm import LlmCompletion, LlmResponseError
from crm_copilot.schema import CopilotRequest
from crm_copilot.service import prepare_reply


class StubLlm:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int, response_format: dict[str, object] | None = None
    ) -> LlmCompletion:
        assert "allowed_evidence_paths" in user_prompt
        assert response_format is not None
        return LlmCompletion(json.dumps(self.payload), "fake/crm", None, None)

    def close(self) -> None:
        pass


def generated(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "summary": "Клиент уточнил состояние заявки.",
        "summary_evidence": ["history.m1.text"],
        "missing_data": [],
        "next_actions": [],
        "reply_draft": "Заявка находится на проверке документов.",
        "reply_evidence": ["application.status"],
    }
    result.update(overrides)
    return result


def request(**overrides: object) -> CopilotRequest:
    payload: dict[str, object] = {
        "case_id": "DEMO-CRM-1",
        "customer_question": "Какой статус заявки?",
        "history": [{"message_id": "m1", "author": "customer", "text": "Какой статус?"}],
        "application": {"status": "document_review"},
    }
    payload.update(overrides)
    return CopilotRequest.model_validate(payload)


def test_ready_reply_uses_confirmed_context() -> None:
    response = prepare_reply(request(), StubLlm(generated()))
    assert response.answerability == "ready"
    assert response.reply_evidence == ["application.status"]
    assert response.requires_employee_confirmation


def test_present_required_field_keeps_value_evidence() -> None:
    response = prepare_reply(
        request(
            required_fields=[
                {
                    "path": "application.status",
                    "label": "Статус заявки",
                    "reason": "Нужен для ответа.",
                    "obtain_from": "backend",
                }
            ]
        ),
        StubLlm(generated(summary_evidence=["application.status"])),
    )
    assert response.summary_evidence == ["application.status"]


def test_required_field_blocks_final_answer_even_if_llm_misses_it() -> None:
    response = prepare_reply(
        request(
            required_fields=[
                {
                    "path": "application.decision",
                    "label": "Решение по заявке",
                    "reason": "Клиент спрашивает об итоговом решении.",
                    "obtain_from": "backend",
                }
            ]
        ),
        StubLlm(generated(reply_draft="Кредит одобрен.", reply_evidence=["invented.path"])),
    )
    assert response.answerability == "needs_data"
    assert response.missing_data[0].path == "application.decision"
    assert "Кредит одобрен" not in response.reply_draft
    assert response.next_actions[0].text == "Получить из CRM: Решение по заявке."
    assert "Мы уточняем решение по заявке" in response.reply_draft


def test_customer_message_cannot_be_evidence_for_final_reply() -> None:
    with pytest.raises(LlmResponseError, match="Сообщение клиента"):
        prepare_reply(request(), StubLlm(generated(reply_evidence=["history.m1.text"])))


def test_present_but_pending_value_still_blocks_final_answer() -> None:
    response = prepare_reply(
        request(
            application={"status": "document_review", "decision": "pending"},
            required_fields=[
                {
                    "path": "application.decision",
                    "label": "Итоговое решение",
                    "reason": "Пока решение не принято.",
                    "obtain_from": "backend",
                    "acceptable_values": ["approved", "declined"],
                }
            ],
        ),
        StubLlm(generated()),
    )
    assert response.answerability == "needs_data"
    assert response.missing_data[0].path == "application.decision"


def test_only_customer_chat_does_not_make_reply_ready() -> None:
    response = prepare_reply(request(application=None), StubLlm(generated(reply_evidence=[])))
    assert response.answerability == "needs_data"
    assert response.missing_data[0].path == "case_context"
    assert response.reply_evidence == []


def test_missing_required_path_is_cited_as_requirement_not_as_value() -> None:
    response = prepare_reply(
        request(
            required_fields=[
                {
                    "path": "verified_facts.deadline.text",
                    "label": "Срок решения",
                    "reason": "Нужен для ответа.",
                    "obtain_from": "backend",
                }
            ]
        ),
        StubLlm(
            generated(
                summary_evidence=["verified_facts.deadline.text"],
                next_actions=[{"text": "Уточнить срок.", "evidence": ["verified_facts.deadline.text"]}],
            )
        ),
    )
    assert response.summary_evidence == ["required_fields[0].path"]
    assert response.next_actions[0].evidence == ["required_fields[0].path"]


def test_missing_customer_data_asks_customer_instead_of_backend() -> None:
    response = prepare_reply(
        request(),
        StubLlm(
            generated(
                missing_data=[
                    {
                        "path": "profile.monthly_revenue",
                        "label": "Выручка за месяц",
                        "reason": "Нужна для ответа.",
                        "obtain_from": "customer",
                    }
                ]
            )
        ),
    )
    assert response.next_actions[0].text == "Запросить у клиента: Выручка за месяц."
    assert "пожалуйста, уточните" in response.reply_draft


def test_unknown_evidence_is_rejected() -> None:
    with pytest.raises(LlmResponseError, match="вне снимка"):
        prepare_reply(request(), StubLlm(generated(summary_evidence=["application.fiction"])))
