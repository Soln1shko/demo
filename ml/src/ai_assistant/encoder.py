"""Реальный локальный multilingual encoder на ONNX через FastEmbed."""

from __future__ import annotations

from fastembed import TextEmbedding

from ai_assistant.config import EMBEDDING_CACHE_PATH, EMBEDDING_MODEL


class MultilingualEncoder:
    """Загружает настоящую multilingual-модель в игнорируемый cache проекта.

    Attributes:
        _model: Загруженная модель.
    """

    def __init__(self) -> None:
        """Инициализирует объект и его зависимости."""
        self._model = TextEmbedding(model_name=EMBEDDING_MODEL, cache_dir=str(EMBEDDING_CACHE_PATH))

    @property
    def dimension(self) -> int:
        """Возвращает размер вектора, с которым создаётся Qdrant-коллекция.

        Returns:
            int: Вычисленное целое значение.
        """
        return self._model.embedding_size

    def encode(self, text: str) -> list[float]:
        """Строит dense-вектор русского или английского текста без внешнего API.

        Args:
            text: Текст сообщения или факта.

        Returns:
            list[float]: Числовые кандидаты.
        """
        return [float(value) for value in next(iter(self._model.embed([text])))]
