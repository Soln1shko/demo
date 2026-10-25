"""Типы знаний и результатов гибридного поиска."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Один проверяемый фрагмент базы знаний с источником и датой среза.

    Attributes:
        knowledge_id: Идентификатор знания.
        title: Название знания.
        text: Текст сообщения или факта.
        category: Категория документа.
        source_url: Ссылка на первоисточник.
        effective_at: Дата актуальности знания.
    """

    knowledge_id: str
    title: str
    text: str
    category: str
    source_url: str
    effective_at: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Фрагмент, который можно передать LLM как контекст ответа.

    Attributes:
        document: Документ базы знаний.
        score: Оценка релевантности или риска.
    """

    document: KnowledgeDocument
    score: float
