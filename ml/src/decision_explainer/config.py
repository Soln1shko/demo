"""Ограничения текста объяснения отказа."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExplanationConfig:
    """Настройки генерации объяснения отказа.

    Attributes:
        max_output_tokens: Максимальное число токенов ответа LLM.
        max_scoring_factors: Максимальное число факторов скоринга в контексте.
    """

    max_output_tokens: int = 350
    max_scoring_factors: int = 2


CONFIG = ExplanationConfig()
