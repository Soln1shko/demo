"""Лимиты обработки документов и контекста LLM."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParserConfig:
    """Лимиты и настройки обработки документов.

    Attributes:
        max_documents: Максимальное число файлов в запросе.
        max_document_bytes: Максимальный размер одного файла в байтах.
        max_pages_per_document: Максимальное число страниц в одном документе.
        max_ocr_characters: Лимит символов распознанного текста.
        max_output_tokens: Максимальное число токенов ответа LLM.
        max_extraction_attempts: Число попыток получить профиль корректного формата без повторного OCR.
    """

    max_documents: int = 8
    max_document_bytes: int = 10_000_000
    max_pages_per_document: int = 20
    max_ocr_characters: int = 60_000
    max_output_tokens: int = 1400
    max_extraction_attempts: int = 2


CONFIG = ParserConfig()
