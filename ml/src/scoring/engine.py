"""Чистый inference логистической модели без библиотек машинного обучения."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from scoring.config import LEGAL_FORMS, MODEL_PATH, PRODUCT_IDS
from scoring.schema import FactorContribution, ScoringInput, ScoringResult


@dataclass(frozen=True, slots=True)
class ModelWeights:
    """Сериализуемый контракт весов, общий для backend и browser-калькулятора.

    Attributes:
        version: Версия модели или набора правил.
        intercept: Свободный член модели.
        numeric_weights: Веса числовых признаков.
        numeric_means: Средние числовых признаков.
        numeric_scales: Масштабы числовых признаков.
        categorical_weights: Веса категориальных признаков.
        risk_bands: Пороги категорий риска.
    """

    version: str
    intercept: float
    numeric_weights: Mapping[str, float]
    numeric_means: Mapping[str, float]
    numeric_scales: Mapping[str, float]
    categorical_weights: Mapping[str, Mapping[str, float]]
    risk_bands: tuple[tuple[float, str], ...]


class ScoringEngine:
    """Вычисляет риск синхронно: один вызов не делает I/O и не вызывает сеть.

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
    def from_json(cls, path: Path = MODEL_PATH) -> ScoringEngine:
        """Загружает компактные веса один раз при старте приложения.

        Args:
            path: Путь к полю или файлу.

        Returns:
            ScoringEngine: Движок со скоринговыми весами.
        """
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            ModelWeights(
                version=payload["version"],
                intercept=float(payload["intercept"]),
                numeric_weights=payload["numeric_weights"],
                numeric_means=payload["numeric_means"],
                numeric_scales=payload["numeric_scales"],
                categorical_weights=payload["categorical_weights"],
                risk_bands=tuple((float(item["upper_bound"]), item["name"]) for item in payload["risk_bands"]),
            )
        )

    def score(self, request: ScoringInput) -> ScoringResult:
        """Возвращает вероятность риска и факторы для показа в калькуляторе.

        Args:
            request: Проверенные входные данные.

        Returns:
            ScoringResult: Вероятность риска и вклады факторов.
        """
        values = _numeric_values(request)
        _validate(request, values)
        contributions = [FactorContribution("intercept", self._weights.intercept)]
        logit = self._weights.intercept
        for feature, value in values.items():
            normalized = (value - self._weights.numeric_means[feature]) / self._weights.numeric_scales[feature]
            contribution = normalized * self._weights.numeric_weights[feature]
            contributions.append(FactorContribution(feature, contribution))
            logit += contribution
        for feature, category in _categorical_values(request).items():
            contribution = self._weights.categorical_weights[feature].get(category, 0.0)
            contributions.append(FactorContribution(f"{feature}:{category}", contribution))
            logit += contribution
        probability = _sigmoid(logit)
        return ScoringResult(
            risk_probability=probability,
            risk_band=_risk_band(probability, self._weights.risk_bands),
            factors=tuple(sorted(contributions, key=lambda item: abs(item.contribution), reverse=True)[:3]),
            model_version=self._weights.version,
        )

    def browser_payload(self) -> dict[str, object]:
        """Возвращает JSON-совместимые веса для единовременной загрузки в браузер.

        Returns:
            dict[str, object]: Структурированные данные для API или LLM.
        """
        return {
            "version": self._weights.version,
            "intercept": self._weights.intercept,
            "numeric_weights": dict(self._weights.numeric_weights),
            "numeric_means": dict(self._weights.numeric_means),
            "numeric_scales": dict(self._weights.numeric_scales),
            "categorical_weights": {key: dict(value) for key, value in self._weights.categorical_weights.items()},
            "risk_bands": [
                {"upper_bound": upper_bound, "name": name} for upper_bound, name in self._weights.risk_bands
            ],
        }


def _numeric_values(request: ScoringInput) -> dict[str, float]:
    """Собирает числовые признаки скоринга.

    Args:
        request: Проверенные входные данные.

    Returns:
        dict[str, float]: Числовые признаки или оценки по имени.
    """
    return {
        "requested_amount": float(request.requested_amount),
        "term_months": float(request.term_months),
        "business_age_months": float(request.business_age_months),
        "monthly_revenue": float(request.monthly_revenue),
        "net_margin_percent": request.net_margin_percent,
        "debt_to_revenue_ratio": request.debt_to_revenue_ratio,
        "credit_history_score": float(request.credit_history_score),
        "has_overdue_debt": float(request.has_overdue_debt),
        "has_collateral": float(request.has_collateral),
    }


def _categorical_values(request: ScoringInput) -> dict[str, str]:
    """Собирает категориальные признаки скоринга.

    Args:
        request: Проверенные входные данные.

    Returns:
        dict[str, str]: Строковые атрибуты по имени.
    """
    return {"product_id": request.product_id, "legal_form": request.legal_form}


def _validate(request: ScoringInput, values: Mapping[str, float]) -> None:
    """Проверяет ограничения доменного контракта.

    Args:
        request: Проверенные входные данные.
        values: Значения признаков.

    Raises:
        ValueError: Входные данные нарушают ограничения домена.
    """
    if request.product_id not in PRODUCT_IDS:
        raise ValueError("Неизвестный product_id для демонстрационной модели.")
    if request.legal_form not in LEGAL_FORMS:
        raise ValueError("legal_form должен быть ip или ooo.")
    if any(value < 0 for value in values.values()):
        raise ValueError("Числовые признаки не могут быть отрицательными.")
    if not 0 <= request.net_margin_percent <= 100:
        raise ValueError("net_margin_percent должен быть в диапазоне 0..100.")
    if not 0 <= request.credit_history_score <= 1000:
        raise ValueError("credit_history_score должен быть в диапазоне 0..1000.")


def _sigmoid(value: float) -> float:
    """Вычисляет устойчивую сигмоиду.

    Args:
        value: Значение факта или признака.

    Returns:
        float: Вычисленное числовое значение.
    """
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _risk_band(probability: float, bands: tuple[tuple[float, str], ...]) -> str:
    """Определяет категорию риска по вероятности.

    Args:
        probability: Вероятность риска.
        bands: Пороги категорий риска.

    Returns:
        str: Сформированный текст.
    """
    return next(name for upper_bound, name in bands if probability <= upper_bound)
