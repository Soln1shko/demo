"""Startup-точка ассистента и RRF-объединение Qdrant/BM25 результатов."""

from __future__ import annotations

from ai_assistant.bm25 import Bm25Index
from ai_assistant.config import RRF_K, QdrantSettings
from ai_assistant.dependencies import AssistantDependencies
from ai_assistant.schema import SearchResult
from ai_assistant.store import KnowledgeStore


class KnowledgeAssistant:
    """Подготавливает источники для будущего LLM-ответа, но не выдумывает ответ сам.

    Attributes:
        _store: Хранилище знаний.
        _bm25: Лексический индекс BM25.
        _documents_by_id: Документы по идентификатору.
    """

    def __init__(self, store: KnowledgeStore, bm25: Bm25Index, documents_by_id: dict[str, SearchResult]) -> None:
        """Инициализирует объект и его зависимости.

        Args:
            store: Хранилище знаний.
            bm25: Лексический индекс BM25.
            documents_by_id: Найденные документы по их идентификаторам.
        """
        self._store = store
        self._bm25 = bm25
        self._documents_by_id = documents_by_id

    def retrieve(self, query: str, limit: int = 5) -> tuple[SearchResult, ...]:
        """Возвращает гибридно ранжированный контекст с обязательными ссылками.

        Args:
            query: Поисковый запрос.
            limit: Ограничение числа результатов.

        Returns:
            tuple[SearchResult, ...]: Найденные фрагменты с оценками.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        if not query.strip():
            raise ValueError("Вопрос не может быть пустым.")
        if limit < 1:
            raise ValueError("limit должен быть положительным.")
        dense = self._store.dense_search(query, limit * 3)
        lexical_ids = self._bm25.search(query, limit * 3)
        ranks: dict[str, float] = {}
        for rank, result in enumerate(dense, start=1):
            ranks[result.document.knowledge_id] = ranks.get(result.document.knowledge_id, 0.0) + 1 / (RRF_K + rank)
        for rank, knowledge_id in enumerate(lexical_ids, start=1):
            ranks[knowledge_id] = ranks.get(knowledge_id, 0.0) + 1 / (RRF_K + rank)
        return tuple(
            SearchResult(document=self._documents_by_id[knowledge_id].document, score=score)
            for knowledge_id, score in sorted(ranks.items(), key=lambda item: (-item[1], item[0]))[:limit]
        )

    def close(self) -> None:
        """Освобождает ресурсы Qdrant при остановке HTTP-сервиса."""
        self._store.close()


def create_assistant(settings: QdrantSettings | None = None) -> KnowledgeAssistant:
    """Создаёт ассистента на старте API и инициализирует его зависимости.

    Args:
        settings: Явные настройки Qdrant для локального запуска или тестов.

    Returns:
        Готовый к hybrid-поиску ассистент.
    """
    dependencies = (
        AssistantDependencies.from_settings(settings)
        if settings is not None
        else AssistantDependencies.from_environment()
    )
    documents_by_id = {item.knowledge_id: SearchResult(document=item, score=0.0) for item in dependencies.documents}
    return KnowledgeAssistant(dependencies.store, dependencies.bm25, documents_by_id)
