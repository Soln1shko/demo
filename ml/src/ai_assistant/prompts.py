"""Промпт и проверяемые ссылки для RAG-ответов ассистента."""

from __future__ import annotations

import re
from collections.abc import Sequence

from ai_assistant.schema import SearchResult

_CITATION_RE = re.compile(r"\[([a-z0-9._-]+)\]", re.IGNORECASE)

ASSISTANT_SYSTEM_PROMPT = """Ты помощник малого бизнеса. Отвечай только по переданному контексту.
Не придумывай условия продуктов, нормы права, тарифы или решение банка. Если контекста недостаточно,
прямо скажи это. Пиши по-русски, кратко и практически. Верни JSON с текстом ответа и
knowledge_ids использованных фрагментов. Не добавляй ссылки в сам текст ответа."""


def assistant_response_format(sources: Sequence[SearchResult]) -> dict[str, object]:
    """Ограничивает JSON-ответ идентификаторами найденных фрагментов.

    Args:
        sources: Найденные источники ответа.

    Returns:
        dict[str, object]: JSON Schema для OpenRouter.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "assistant_answer",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "knowledge_ids": {
                        "type": "array",
                        "items": {"type": "string", "enum": [item.document.knowledge_id for item in sources]},
                    },
                },
                "required": ["answer", "knowledge_ids"],
                "additionalProperties": False,
            },
        },
    }


def assistant_prompt(question: str, sources: Sequence[SearchResult]) -> str:
    """Собирает вопрос и найденные RAG-фрагменты для генерации ответа.

    Args:
        question: Вопрос клиента.
        sources: Найденные источники ответа.

    Returns:
        str: Сформированный текст.
    """
    context = "\n\n".join(
        f"knowledge_id: {item.document.knowledge_id}\n"
        f"title: {item.document.title}\n"
        f"text: {item.document.text}\n"
        f"source_url: {item.document.source_url}\n"
        f"effective_at: {item.document.effective_at}"
        for item in sources
    )
    return f"Вопрос пользователя:\n{question}\n\nКонтекст:\n{context}"


def cited_knowledge_ids(answer: str) -> set[str]:
    """Возвращает knowledge_id, которые LLM явно связала со своим ответом.

    Args:
        answer: Готовый ответ клиенту.

    Returns:
        set[str]: Множество допустимых путей к полям.
    """
    return set(_CITATION_RE.findall(answer))
