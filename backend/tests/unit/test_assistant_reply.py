from unittest.mock import AsyncMock

import pytest

from app.services import assistant


@pytest.mark.asyncio
async def test_search_fragments_never_become_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assistant.ml, "assistant_answer", AsyncMock(return_value=None))
    search = AsyncMock(
        return_value=[{"document": {"text": "Признаки применимости: ip, ooo.", "title": "Кредит"}}]
    )
    monkeypatch.setattr(
        assistant.ml,
        "assistant_search",
        search,
    )
    monkeypatch.setattr(assistant, "ask_llm", AsyncMock(return_value=None))
    assert await assistant._ml_reply("Какие условия кредита?") is None
    search.assert_not_awaited()


@pytest.mark.asyncio
async def test_internal_codes_from_model_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        assistant.ml,
        "assistant_answer",
        AsyncMock(return_value={"answer": "Типовые цели: working_capital, equipment.", "sources": []}),
    )
    assert await assistant._ml_reply("Для чего кредит?") is None


@pytest.mark.asyncio
async def test_only_cited_human_readable_sources_are_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        assistant.ml,
        "assistant_answer",
        AsyncMock(
            return_value={
                "answer": "Срок до 12 месяцев. [credit.alfa_start.term]",
                "sources": [
                    {"document": {"knowledge_id": "credit.alfa_start.term", "title": "Альфа-Старт: term"}},
                    {
                        "document": {
                            "knowledge_id": "credit.alfa_start.purpose",
                            "title": "Альфа-Старт: purpose",
                        }
                    },
                ],
            }
        ),
    )
    assert await assistant._ml_reply("Какой срок?") == ("Срок до 12 месяцев.\n\nИсточники: Альфа-Старт", "ml")
