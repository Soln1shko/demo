"""OCR, извлечение LLM и проверка происхождения полей профиля."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from app.llm import ChatCompletionClient, LlmResponseError
from app.llm_json import json_payload
from document_parser.config import CONFIG, ParserConfig
from document_parser.ocr import DocumentOcr
from document_parser.prompts import RESPONSE_FORMAT, SYSTEM_PROMPT, document_prompt
from document_parser.schema import DocumentParseResponse, ParsedProfile


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Загруженный документ с демонстрационным идентификатором.

    Attributes:
        document_id: Идентификатор загруженного документа.
        filename: Имя файла.
        content: Содержимое ответа или документа.
    """

    document_id: str
    filename: str
    content: bytes


def parse_documents(
    case_id: str,
    documents: list[SourceDocument],
    ocr: DocumentOcr,
    llm: ChatCompletionClient,
    config: ParserConfig = CONFIG,
) -> DocumentParseResponse:
    """Извлекает профиль и проверяет ссылки на документы.

    Args:
        case_id: Демонстрационный идентификатор заявки.
        documents: Документы для обработки или поиска.
        ocr: Сервис распознавания документов.
        llm: Клиент языковой модели.
        config: Типизированные настройки сервиса.

    Returns:
        DocumentParseResponse: Профиль с источниками, конфликтами и пробелами.

    Raises:
        ValueError: Входные данные нарушают ограничения домена.
        LlmResponseError: Ответ LLM нарушает формат или ссылается на неподтверждённые данные.
    """
    if not 1 <= len(documents) <= config.max_documents:
        raise ValueError("Нужно загрузить от 1 до 8 документов.")
    pages: list[dict[str, object]] = []
    page_lookup: dict[tuple[str, int], str] = {}
    for document in documents:
        suffix = _validated_suffix(document.filename, document.content, config.max_document_bytes)
        extracted = ocr.extract(document.content, suffix)
        if not extracted or len(extracted) > config.max_pages_per_document:
            raise ValueError("Документ пустой или содержит слишком много страниц.")
        for page in extracted:
            if not page.text.strip():
                continue
            key = (document.document_id, page.page)
            page_lookup[key] = page.text
            pages.append({"document_id": document.document_id, "page": page.page, "text": page.text})
    if not pages:
        raise ValueError("OCR не извлёк текст из документов.")
    if sum(len(str(page["text"])) for page in pages) > config.max_ocr_characters:
        raise ValueError("Слишком большой объём распознанного текста.")
    for attempt in range(config.max_extraction_attempts):
        completion = llm.complete(
            SYSTEM_PROMPT,
            document_prompt(pages),
            config.max_output_tokens,
            response_format=RESPONSE_FORMAT,
        )
        try:
            parsed = ParsedProfile.model_validate_json(json_payload(completion.content))
            break
        except (ValidationError, LlmResponseError) as error:
            if attempt + 1 == config.max_extraction_attempts:
                raise LlmResponseError("OpenRouter вернул неверный формат профиля.") from error
    else:
        raise LlmResponseError("Не задано ни одной попытки извлечения профиля.")
    for evidence in parsed.field_evidence:
        _check_source(evidence.document_id, evidence.page, evidence.source_text, page_lookup)
    for fact in parsed.additional_facts:
        _check_source(fact.document_id, fact.page, fact.source_text, page_lookup)
    fields = parsed.profile.model_dump()
    return DocumentParseResponse(
        case_id=case_id,
        profile=parsed.profile,
        additional_facts=parsed.additional_facts,
        field_evidence=parsed.field_evidence,
        conflicts=parsed.conflicts,
        missing_fields=[name for name, value in fields.items() if value is None],
        model=completion.model,
    )


def _validated_suffix(filename: str, content: bytes, maximum: int) -> str:
    """Проверяет размер и сигнатуру файла.

    Args:
        filename: Имя загруженного файла.
        content: Содержимое файла или ответа.
        maximum: Предельный размер файла.

    Returns:
        str: Сформированный текст.

    Raises:
        ValueError: Входные данные нарушают ограничения домена.
    """
    if not content or len(content) > maximum:
        raise ValueError("Размер документа превышает допустимый лимит или файл пустой.")
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    signatures = {".pdf": (b"%PDF",), ".png": (b"\x89PNG",), ".jpg": (b"\xff\xd8",), ".jpeg": (b"\xff\xd8",)}
    if suffix not in signatures or not content.startswith(signatures[suffix]):
        raise ValueError("Поддерживаются только PDF, PNG и JPEG с корректной сигнатурой.")
    return suffix


def _normalized(value: str) -> str:
    """Нормализует пробелы и регистр для сопоставления источника.

    Args:
        value: Значение факта или признака.

    Returns:
        str: Сформированный текст.
    """
    return " ".join(value.casefold().split())


def _check_source(document_id: str, page: int, source_text: str, pages: dict[tuple[str, int], str]) -> None:
    """Проверяет ссылку LLM на распознанный текст.

    Args:
        document_id: Идентификатор загруженного документа.
        page: Номер страницы документа.
        source_text: Цитата, указанная языковой моделью.
        pages: Распознанный текст по документам и страницам.

    Raises:
        LlmResponseError: Невозможно обработать ответ внешнего сервиса.
    """
    source = pages.get((document_id, page))
    if source is None or _normalized(source_text) not in _normalized(source):
        raise LlmResponseError("OpenRouter сослался на текст вне загруженных документов.")
