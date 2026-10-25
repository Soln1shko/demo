"""Локальный PaddleOCR для кириллицы и таблиц в PDF и изображениях."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class OcrPage:
    """Одна распознанная страница документа.

    Attributes:
        page: Страница.
        text: Текст.
    """

    page: int
    text: str


class DocumentOcr(Protocol):
    """Контракт OCR-сервиса."""

    def extract(self, content: bytes, suffix: str) -> list[OcrPage]:
        """Распознаёт текст и таблицы документа.

        Args:
            content: Содержимое файла или ответа.
            suffix: Расширение файла.

        Returns:
            list[OcrPage]: Распознанные страницы.
        """
        ...


class _PaddlePipeline(Protocol):
    """Контракт PaddleOCR pipeline."""

    def predict(self, path: str, **kwargs: object) -> Any:
        """Распознаёт содержимое страниц.

        Args:
            path: Путь к полю или файлу.
            kwargs: Параметры распознавания PaddleOCR.

        Returns:
            Any: Ответ сторонней OCR-библиотеки.
        """
        ...


class PaddleDocumentOcr:
    """Сначала запускает лёгкий текстовый OCR; структуру загружает только если текст не распознан.

    Attributes:
        _pipeline: Модель структуры документа с отложенной загрузкой.
        _text_pipeline: Модель распознавания текста с отложенной загрузкой.
        _lock: Блокировка доступа к моделям OCR.
    """

    def __init__(self) -> None:
        """Создаёт OCR-адаптер с отложенной загрузкой модели."""
        self._pipeline: _PaddlePipeline | None = None
        self._text_pipeline: _PaddlePipeline | None = None
        self._lock = Lock()

    def extract(self, content: bytes, suffix: str) -> list[OcrPage]:
        """Распознаёт текст и таблицы документа.

        Args:
            content: Содержимое файла или ответа.
            suffix: Расширение файла.

        Returns:
            list[OcrPage]: Распознанные страницы.
        """
        with self._lock:
            return self._extract_locked(content, suffix)

    def _extract_locked(self, content: bytes, suffix: str) -> list[OcrPage]:
        """Выполняет OCR под блокировкой модели.

        Args:
            content: Содержимое файла или ответа.
            suffix: Расширение файла.

        Returns:
            list[OcrPage]: Распознанные страницы.
        """
        if self._text_pipeline is None:
            from paddleocr import PaddleOCR  # type: ignore[import-untyped]

            self._text_pipeline = PaddleOCR(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="cyrillic_PP-OCRv5_mobile_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                device="cpu",
            )
        with TemporaryDirectory(prefix="demo-document-") as directory:
            path = Path(directory) / f"input{suffix}"
            path.write_bytes(content)
            pages = [
                OcrPage(page=number, text=_ocr_rows(result.json["res"]))
                for number, result in enumerate(self._text_pipeline.predict(str(path)), start=1)
            ]
            if any(page.text.strip() for page in pages):
                return pages
            if self._pipeline is None:
                from paddleocr import PPStructureV3  # type: ignore[import-untyped]

                self._pipeline = PPStructureV3(
                    text_recognition_model_name="cyrillic_PP-OCRv5_mobile_rec",
                    layout_detection_model_name="PP-DocLayout-M",
                    text_detection_model_name="PP-OCRv5_mobile_det",
                    use_table_recognition=True,
                    use_region_detection=False,
                    use_formula_recognition=False,
                    use_chart_recognition=False,
                    use_seal_recognition=False,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    device="cpu",
                )
            structured = self._pipeline.predict(str(path))
            return [
                OcrPage(page=number, text=str(result.markdown.get("markdown_texts", "")).strip())
                for number, result in enumerate(structured, start=1)
            ]


def _ocr_rows(result: dict[str, object]) -> str:
    """Собирает текстовые строки результата OCR.

    Args:
        result: Результат внешнего сервиса.

    Returns:
        str: Сформированный текст.
    """
    texts = result.get("rec_texts", [])
    boxes = result.get("rec_boxes", [])
    if hasattr(boxes, "tolist"):
        boxes = boxes.tolist()
    if not isinstance(texts, list) or not isinstance(boxes, list):
        return ""
    cells: list[tuple[int, int, str]] = []
    for text, box in zip(texts, boxes, strict=False):
        if isinstance(text, str) and isinstance(box, (list, tuple)) and len(box) >= 4:
            x1, y1, _, y2 = box[:4]
            cells.append(((int(y1) + int(y2)) // 2, int(x1), text))
    cells.sort()
    rows: list[list[tuple[int, str]]] = []
    row_y: list[int] = []
    for y, x, value in cells:
        if not rows or abs(y - row_y[-1]) > 20:
            rows.append([])
            row_y.append(y)
        rows[-1].append((x, value))
    return "\n".join(" | ".join(value for _, value in sorted(row)) for row in rows)
