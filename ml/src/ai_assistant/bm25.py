"""Небольшой BM25-индекс для lexical части гибридного поиска."""

from __future__ import annotations

import numpy as np
from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from ai_assistant.config import TOKEN_RE
from ai_assistant.schema import KnowledgeDocument


class Bm25Index:
    """Индексирует corpus в памяти и ранжирует документы по BM25.

    Attributes:
        _documents: Индексируемые документы.
        _model: Загруженная модель.
    """

    def __init__(self, documents: tuple[KnowledgeDocument, ...]) -> None:
        """Инициализирует объект и его зависимости.

        Args:
            documents: Документы для обработки или поиска.
        """
        self._documents = documents
        self._model = BM25Okapi([_tokens(_full_text(item)) for item in documents])

    def search(self, query: str, limit: int) -> tuple[str, ...]:
        """Возвращает ID документов по убыванию lexical-релевантности.

        Args:
            query: Поисковый запрос.
            limit: Ограничение числа результатов.

        Returns:
            tuple[str, ...]: Строковые значения.
        """
        scores: np.ndarray = self._model.get_scores(_tokens(query))
        scored = [
            (document.knowledge_id, float(score)) for document, score in zip(self._documents, scores, strict=True)
        ]
        return tuple(
            document_id
            for document_id, score in sorted(scored, key=lambda item: (-item[1], item[0]))[:limit]
            if score > 0
        )


def _full_text(document: KnowledgeDocument) -> str:
    """Собирает индексируемый текст документа.

    Args:
        document: Документ базы знаний.

    Returns:
        str: Сформированный текст.
    """
    return f"{document.title} {document.text} {document.category}"


def _tokens(value: str) -> list[str]:
    """Сближает русские словоформы для лексического поиска.

    Args:
        value: Поисковый запрос или текст фрагмента.

    Returns:
        list[str]: Токены с короткой основой длинных русских слов.
    """
    return [
        token[:6] if len(token) >= 7 and "а" <= token[0] <= "я" else token
        for token in TOKEN_RE.findall(value.casefold())
    ]
