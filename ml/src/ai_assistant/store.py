"""Qdrant-адаптер: создание коллекции, идемпотентный seed и dense поиск."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from ai_assistant.config import KNOWLEDGE_COLLECTION, QdrantSettings
from ai_assistant.encoder import MultilingualEncoder
from ai_assistant.schema import KnowledgeDocument, SearchResult


class KnowledgeStore:
    """Хранит dense-векторы знаний в Qdrant и возвращает результаты поиска.

    Attributes:
        _client: Клиент хранилища Qdrant.
        _encoder: Энкодер запросов и документов.
        _collection_name: Имя коллекции Qdrant.
    """

    def __init__(
        self, client: QdrantClient, encoder: MultilingualEncoder, collection_name: str = KNOWLEDGE_COLLECTION
    ) -> None:
        """Инициализирует объект и его зависимости.

        Args:
            client: Клиент хранилища Qdrant.
            encoder: Энкодер запросов и документов.
            collection_name: Имя коллекции Qdrant.
        """
        self._client = client
        self._encoder = encoder
        self._collection_name = collection_name

    @classmethod
    def from_settings(cls, settings: QdrantSettings) -> KnowledgeStore:
        """Подключается к контейнеру Qdrant или локальному dev-хранилищу.

        Args:
            settings: Настройки внешней зависимости.

        Returns:
            KnowledgeStore: Хранилище с подключением к Qdrant.
        """
        client = QdrantClient(url=settings.url) if settings.url else QdrantClient(path=str(settings.local_path))
        return cls(client, MultilingualEncoder())

    def seed(self, documents: tuple[KnowledgeDocument, ...]) -> int:
        """Создаёт коллекцию при первом запуске и идемпотентно обновляет знания.

        Args:
            documents: Документы для обработки или поиска.

        Returns:
            int: Вычисленное целое значение.
        """
        if not self._client.collection_exists(self._collection_name):
            self._client.create_collection(
                self._collection_name,
                vectors_config=models.VectorParams(size=self._encoder.dimension, distance=models.Distance.COSINE),
            )
        self._client.upsert(
            self._collection_name,
            points=[
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, document.knowledge_id)),
                    vector=self._encoder.encode(f"{document.title} {document.text}"),
                    payload={
                        "knowledge_id": document.knowledge_id,
                        "title": document.title,
                        "text": document.text,
                        "category": document.category,
                        "source_url": document.source_url,
                        "effective_at": document.effective_at,
                    },
                )
                for document in documents
            ],
            wait=True,
        )
        return self._client.count(self._collection_name, exact=True).count

    def close(self) -> None:
        """Закрывает локальный или сетевой клиент Qdrant."""
        self._client.close()

    def dense_search(self, query: str, limit: int) -> tuple[SearchResult, ...]:
        """Ищет в Qdrant semantic-кандидатов по dense вектору запроса.

        Args:
            query: Поисковый запрос.
            limit: Ограничение числа результатов.

        Returns:
            tuple[SearchResult, ...]: Найденные фрагменты с оценками.
        """
        response = self._client.query_points(
            self._collection_name,
            query=self._encoder.encode(query),
            limit=limit,
            with_payload=True,
        )
        return tuple(_search_result(point.payload, point.score) for point in response.points)


def _search_result(payload: dict[str, object] | None, score: float) -> SearchResult:
    """Собирает типизированный результат из записи Qdrant.

    Args:
        payload: Тело запроса или ответа.
        score: Оценка релевантности или риска.

    Returns:
        SearchResult: Найденный документ с оценкой.

    Raises:
        RuntimeError: Операция завершилась ошибкой.
    """
    if payload is None:
        raise RuntimeError("Qdrant вернул результат без payload.")
    return SearchResult(
        document=KnowledgeDocument(
            knowledge_id=str(payload["knowledge_id"]),
            title=str(payload["title"]),
            text=str(payload["text"]),
            category=str(payload["category"]),
            source_url=str(payload["source_url"]),
            effective_at=str(payload["effective_at"]),
        ),
        score=score,
    )
