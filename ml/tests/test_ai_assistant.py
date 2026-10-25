"""Проверяет объём знаний, startup seed и гибридный поиск в embedded Qdrant."""

from pathlib import Path

from ai_assistant.config import QdrantSettings
from ai_assistant.knowledge import build_knowledge
from ai_assistant.service import create_assistant


def test_knowledge_has_at_least_200_unique_documents() -> None:
    documents = build_knowledge()
    assert len(documents) >= 200
    assert len({document.knowledge_id for document in documents}) == len(documents)


def test_startup_seeds_qdrant_and_retrieves_credit_context(tmp_path: Path) -> None:
    assistant = create_assistant(QdrantSettings(url=None, local_path=tmp_path / "qdrant"))
    try:
        results = assistant.retrieve("кредит продавцу маркетплейса на закупку товара", limit=3)
        assert len(results) == 3
        assert all(result.document.source_url.startswith("https://") for result in results)
        assert any("seller_credit" in result.document.knowledge_id for result in results)
        restrictions = assistant.retrieve("Какие ограничения у кредита продавцу маркетплейса?", limit=4)
        assert any("seller_credit" in result.document.knowledge_id for result in restrictions)
    finally:
        assistant.close()
