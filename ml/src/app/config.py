"""Конфигурация внешней LLM для HTTP-сервиса."""

from __future__ import annotations

import os
from dataclasses import dataclass

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3.5-super-vl:free"


@dataclass(frozen=True, slots=True)
class OpenRouterSettings:
    """Настройки OpenRouter, читаемые только из окружения контейнера.

    Attributes:
        api_key: Ключ доступа к OpenRouter.
        model: Название использованной LLM.
        api_url: Адрес API OpenRouter.
        timeout_seconds: Таймаут HTTP-запроса.
    """

    api_key: str | None
    model: str = DEFAULT_OPENROUTER_MODEL
    api_url: str = OPENROUTER_API_URL
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> OpenRouterSettings:
        """Собирает настройки без загрузки ключа в код или репозиторий.

        Returns:
            OpenRouterSettings: Настройки провайдера.
        """
        return cls(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model=os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        )
