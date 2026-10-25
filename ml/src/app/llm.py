"""OpenRouter-клиент и строгие контракты ответа LLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import DEFAULT_OPENROUTER_MODEL, OpenRouterSettings


class LlmUnavailableError(RuntimeError):
    """LLM недоступна из-за отсутствия ключа или сетевой ошибки."""


class LlmResponseError(RuntimeError):
    """OpenRouter вернул ответ, который нельзя использовать в API."""


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    """Нормализованный текстовый ответ и метаданные вызова LLM.

    Attributes:
        content: Содержимое ответа или документа.
        model: Модель.
        input_tokens: Вход токены.
        output_tokens: Выход токены.
    """

    content: str
    model: str
    input_tokens: int | None
    output_tokens: int | None


class ChatCompletionClient(Protocol):
    """Минимальный контракт LLM, пригодный для подмены в интеграционных тестах."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        response_format: dict[str, object] | None = None,
    ) -> LlmCompletion:
        """Генерирует один текстовый ответ по system и user prompt.

        Args:
            system_prompt: Системная инструкция для модели.
            user_prompt: Данные запроса к модели.
            max_tokens: Лимит выходных токенов.
            response_format: Формат структурированного ответа.

        Returns:
            LlmCompletion: Текст и метаданные ответа модели.
        """

    def close(self) -> None:
        """Освобождает сетевые ресурсы клиента."""


class OpenRouterClient:
    """Синхронный OpenAI-совместимый клиент OpenRouter.

    Attributes:
        _settings:  настройки.
        _client:  клиент.
        _owns_client:  owns клиент.
    """

    def __init__(self, settings: OpenRouterSettings, client: httpx.Client | None = None) -> None:
        """Инициализирует объект и его зависимости.

        Args:
            settings: Настройки внешних зависимостей.
            client: Клиент.
        """
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.timeout_seconds)
        self._owns_client = client is None

    @classmethod
    def from_environment(cls) -> OpenRouterClient:
        """Создаёт клиент с моделью и ключом из окружения.

        Returns:
            OpenRouterClient: Клиент с настройками из окружения.
        """
        return cls(OpenRouterSettings.from_environment())

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        response_format: dict[str, object] | None = None,
    ) -> LlmCompletion:
        """Отправляет non-streaming chat completion и возвращает текст ответа.

        Args:
            system_prompt: Системная инструкция для модели.
            user_prompt: Данные запроса к модели.
            max_tokens: Лимит выходных токенов.
            response_format: Формат структурированного ответа.

        Returns:
            LlmCompletion: Текст и метаданные ответа модели.

        Raises:
            LlmUnavailableError: Ключ OpenRouter отсутствует или провайдер недоступен.
        """
        if not self._settings.api_key:
            raise LlmUnavailableError("Не задан OPENROUTER_API_KEY.")
        model_instruction = "\n/no_think" if self._settings.model == "qwen/qwen3-32b" else ""
        try:
            response = self._client.post(
                self._settings.api_url,
                headers={"Authorization": f"Bearer {self._settings.api_key}"},
                json={
                    "model": self._settings.model,
                    "messages": [
                        {"role": "system", "content": system_prompt + model_instruction},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": max_tokens,
                    **({"reasoning": {"enabled": False}} if self._settings.model == DEFAULT_OPENROUTER_MODEL else {}),
                    **(
                        {"response_format": response_format, "provider": {"require_parameters": True}}
                        if response_format is not None
                        else {}
                    ),
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise LlmUnavailableError("OpenRouter временно недоступен.") from error
        return _completion(response.json(), self._settings.model)

    def close(self) -> None:
        """Закрывает собственный HTTP-клиент после остановки сервиса."""
        if self._owns_client:
            self._client.close()


def _completion(payload: object, default_model: str) -> LlmCompletion:
    """Проверяет и извлекает ответ OpenRouter.

    Args:
        payload: Тело запроса или ответа.
        default_model: Имя модели по умолчанию.

    Returns:
        LlmCompletion: Текст и метаданные ответа модели.

    Raises:
        LlmResponseError: Ответ LLM нарушает формат или ссылается на неподтверждённые данные.
    """
    if not isinstance(payload, dict):
        raise LlmResponseError("OpenRouter вернул ответ в неизвестном формате.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise LlmResponseError("OpenRouter не вернул completion.")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise LlmResponseError("OpenRouter не вернул текст completion.")
    usage = payload.get("usage")
    usage_data = usage if isinstance(usage, dict) else {}
    content = message["content"].strip()
    if not content:
        raise LlmResponseError("OpenRouter вернул пустой completion.")
    return LlmCompletion(
        content=content,
        model=str(payload.get("model", default_model)),
        input_tokens=_as_int(usage_data.get("prompt_tokens")),
        output_tokens=_as_int(usage_data.get("completion_tokens")),
    )


def _as_int(value: object) -> int | None:
    """Возвращает целое значение счётчика токенов.

    Args:
        value: Значение факта или признака.

    Returns:
        int | None: Целое значение при наличии.
    """
    return value if isinstance(value, int) else None
