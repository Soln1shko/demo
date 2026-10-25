"""Подготовка зависимостей RAG-ассистента для одного запуска сервиса."""

from __future__ import annotations

from dataclasses import dataclass

from ai_assistant.bm25 import Bm25Index
from ai_assistant.config import QdrantSettings
from ai_assistant.knowledge import build_knowledge
from ai_assistant.schema import KnowledgeDocument
from ai_assistant.store import KnowledgeStore


@dataclass(frozen=True, slots=True)
class AssistantDependencies:
    """Готовые зависимости ассистента, созданные на старте приложения.

    Attributes:
        store: Адаптер Qdrant для semantic-поиска.
        bm25: Локальный индекс lexical-поиска.
        documents: Справочные фрагменты, доступные для выдачи в LLM-контекст.
    """

    store: KnowledgeStore
    bm25: Bm25Index
    documents: tuple[KnowledgeDocument, ...]

    @classmethod
    def from_environment(cls) -> AssistantDependencies:
        """Собирает зависимости из окружения сервиса.

        Returns:
            Готовые хранилище, lexical-индекс и базу знаний.
        """
        return cls.from_settings(QdrantSettings.from_environment())

    @classmethod
    def from_settings(cls, settings: QdrantSettings) -> AssistantDependencies:
        """Собирает зависимости из явных настроек, в том числе для теста.

        Args:
            settings: Режим подключения к Qdrant.

        Returns:
            Готовые зависимости с загруженной базой знаний.

        Raises:
            RuntimeError: Qdrant не сохранил полный набор фрагментов.
        """
        documents = build_knowledge()
        store = KnowledgeStore.from_settings(settings)
        seeded = store.seed(documents)
        if seeded < len(documents):
            store.close()
            raise RuntimeError("Qdrant не сохранил все фрагменты базы знаний.")
        return cls(store=store, bm25=Bm25Index(documents), documents=documents)

    def close(self) -> None:
        """Закрывает соединение с Qdrant при остановке приложения."""
        self.store.close()
