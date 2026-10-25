"""Движок синтетической банковской истории и прогноза кассового разрыва."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cash_cap.bank_data import generate_bank_data
from cash_cap.config import FORECAST_DAYS, HISTORY_DAYS, MODEL_PATH
from cash_cap.features import extract_features
from cash_cap.schema import BankDay, CashGapForecast, CashProfile


@dataclass(frozen=True, slots=True)
class ModelWeights:
    """Компактные веса логистической регрессии риска разрыва.

    Attributes:
        version: Версия модели или набора правил.
        intercept: Свободный член модели.
        weights: Веса признаков модели.
        means: Средние значения признаков модели.
        scales: Масштабы признаков модели.
    """

    version: str
    intercept: float
    weights: Mapping[str, float]
    means: Mapping[str, float]
    scales: Mapping[str, float]


class CashGapEngine:
    """Генерирует историю из профиля и прогнозирует риск на её признаках.

    Attributes:
        _weights: Параметры модели.
    """

    def __init__(self, weights: ModelWeights) -> None:
        """Инициализирует объект и его зависимости.

        Args:
            weights: Веса признаков модели.
        """
        self._weights = weights

    @classmethod
    def from_json(cls, path: Path = MODEL_PATH) -> CashGapEngine:
        """Загружает веса модели один раз при старте приложения.

        Args:
            path: Путь к полю или файлу.

        Returns:
            CashGapEngine: Движок с загруженными весами.
        """
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            ModelWeights(
                version=payload["version"],
                intercept=float(payload["intercept"]),
                weights=payload["weights"],
                means=payload["means"],
                scales=payload["scales"],
            )
        )

    def generate_bank_data(self, profile: CashProfile, days: int = HISTORY_DAYS) -> tuple[BankDay, ...]:
        """Первый шаг движка: локально создаёт синтетическую историю счёта.

        Args:
            profile: Профиль клиента или бизнеса.
            days: Количество дней.

        Returns:
            tuple[BankDay, ...]: Синтетическая история банковских операций.
        """
        return generate_bank_data(profile, days)

    def predict(self, profile: CashProfile, forecast_days: int = FORECAST_DAYS) -> CashGapForecast:
        """Второй шаг: вычисляет риск по сгенерированной истории, без сети и LLM.

        Args:
            profile: Профиль клиента или бизнеса.
            forecast_days: Горизонт прогноза.

        Returns:
            CashGapForecast: Прогноз риска и его факторов.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        if forecast_days < 1:
            raise ValueError("forecast_days должен быть положительным.")
        history = self.generate_bank_data(profile)
        features = extract_features(history)
        probability = _predict_probability(features, self._weights)
        estimated_shortfall = _estimated_shortfall(history, features, forecast_days)
        return CashGapForecast(
            cash_gap_probability=round(probability, 4),
            risk_band=_risk_band(probability),
            estimated_shortfall=estimated_shortfall,
            forecast_days=forecast_days,
            factors=_factors(features),
        )


def _predict_probability(features: Mapping[str, float], model: ModelWeights) -> float:
    """Вычисляет вероятность кассового разрыва.

    Args:
        features: Числовые признаки модели.
        model: Название использованной LLM.

    Returns:
        float: Вычисленное числовое значение.
    """
    logit = model.intercept
    for name, value in features.items():
        logit += ((value - model.means[name]) / model.scales[name]) * model.weights[name]
    return 1 / (1 + math.exp(-logit))


def _estimated_shortfall(history: tuple[BankDay, ...], features: Mapping[str, float], forecast_days: int) -> int:
    """Оценивает величину ожидаемого дефицита.

    Args:
        history: История переписки.
        features: Числовые признаки модели.
        forecast_days: Горизонт прогноза.

    Returns:
        int: Вычисленное целое значение.
    """
    average_net_flow = (history[-1].closing_balance - history[0].closing_balance) / max(len(history) - 1, 1)
    average_outflow = sum(item.outflow for item in history) / len(history)
    volatility_buffer = average_outflow * features["outflow_volatility"] * 2
    projected_balance = history[-1].closing_balance + average_net_flow * forecast_days - volatility_buffer
    return max(0, round(-projected_balance))


def _risk_band(probability: float) -> str:
    """Определяет категорию риска по вероятности.

    Args:
        probability: Вероятность риска.

    Returns:
        str: Сформированный текст.
    """
    if probability <= 0.2:
        return "низкий"
    if probability <= 0.5:
        return "умеренный"
    return "высокий"


def _factors(features: Mapping[str, float]) -> tuple[str, ...]:
    """Собирает вклады факторов в прогноз.

    Args:
        features: Числовые признаки модели.

    Returns:
        tuple[str, ...]: Строковые значения.
    """
    factors: list[str] = []
    if features["current_balance_to_outflow"] < 1:
        factors.append("Остатка на счёте меньше среднего дневного списания.")
    if features["net_cash_flow_ratio"] < 0:
        factors.append("Средние списания выше поступлений.")
    if features["outflow_volatility"] > 0.35:
        factors.append("Списания заметно колеблются.")
    return tuple(factors) or ("По синтетической истории явных факторов разрыва не найдено.",)
