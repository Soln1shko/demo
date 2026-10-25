"""Демонстрационные пороги маршрутизации кейса к аналитику."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UnderwritingConfig:
    """Пороги и настройки анализа заявки.

    Attributes:
        medium_risk_probability: Порог среднего скорингового риска.
        high_risk_probability: Порог высокого скорингового риска.
        high_complexity_issue_count: Число проблемных проверок для высокой сложности.
        micro_medium_exposure_months: Порог среднего приоритета микробизнеса в месячных выручках.
        micro_high_exposure_months: Порог высокого приоритета микробизнеса в месячных выручках.
        small_medium_exposure_months: Порог среднего приоритета малого бизнеса в месячных выручках.
        small_high_exposure_months: Порог высокого приоритета малого бизнеса в месячных выручках.
        max_output_tokens: Максимальное число токенов ответа LLM.
    """

    medium_risk_probability: float = 0.35
    high_risk_probability: float = 0.65
    high_complexity_issue_count: int = 2
    micro_medium_exposure_months: float = 1.0
    micro_high_exposure_months: float = 2.0
    small_medium_exposure_months: float = 2.0
    small_high_exposure_months: float = 4.0
    max_output_tokens: int = 1500


CONFIG = UnderwritingConfig()
