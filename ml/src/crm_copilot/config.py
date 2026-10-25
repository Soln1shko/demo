"""Ограничения ответа CRM Copilot."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CopilotConfig:
    """Настройки генерации CRM-ответа.

    Attributes:
        max_output_tokens: Максимальное число токенов ответа LLM.
    """

    max_output_tokens: int = 1800


CONFIG = CopilotConfig()
