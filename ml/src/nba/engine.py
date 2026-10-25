"""Чистый синхронный inference для next-best-action без внешних вызовов."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from nba.config import LEGAL_FORMS, MODEL_PATH, NON_CREDIT_PRODUCT_IDS, REASONS
from nba.schema import BusinessProfile, Recommendation


@dataclass(frozen=True, slots=True)
class ProductWeights:
    """Веса одной логистической модели релевантности продукта.

    Attributes:
        intercept: Свободный член модели.
        weights: Веса признаков модели.
    """

    intercept: float
    weights: Mapping[str, float]


class NbaEngine:
    """Ранжирует только некредитные продукты МСБ из утверждённого каталога.

    Attributes:
        _version: Версия модели.
        _product_weights: Веса модели по продуктам.
    """

    def __init__(self, version: str, product_weights: Mapping[str, ProductWeights]) -> None:
        """Инициализирует объект и его зависимости.

        Args:
            version: Версия модели или набора правил.
            product_weights: Веса рекомендаций по продуктам.
        """
        self._version = version
        self._product_weights = product_weights

    @classmethod
    def from_json(cls, path: Path = MODEL_PATH) -> NbaEngine:
        """Загружает веса один раз при старте приложения или страницы профиля.

        Args:
            path: Путь к полю или файлу.

        Returns:
            NbaEngine: Движок рекомендаций с весами.
        """
        payload = json.loads(path.read_text(encoding="utf-8"))
        weights = {
            product_id: ProductWeights(intercept=float(value["intercept"]), weights=value["weights"])
            for product_id, value in payload["product_weights"].items()
        }
        return cls(version=payload["version"], product_weights=weights)

    def recommend(self, profile: BusinessProfile, top_n: int = 3) -> tuple[Recommendation, ...]:
        """Возвращает top-N не подключённых сервисов, отсортированных по релевантности.

        Args:
            profile: Профиль клиента или бизнеса.
            top_n: Максимальное число вариантов.

        Returns:
            tuple[Recommendation, ...]: Ранжированные рекомендации.
        """
        _validate(profile, top_n)
        features = _features(profile)
        existing = set(profile.existing_product_ids)
        ranked = [
            Recommendation(product_id=product_id, score=_score(features, weights), reason=REASONS[product_id])
            for product_id, weights in self._product_weights.items()
            if product_id not in existing and _applicable(product_id, profile)
        ]
        return tuple(sorted(ranked, key=lambda item: (-item.score, item.product_id))[:top_n])

    def browser_payload(self) -> dict[str, object]:
        """Отдаёт JSON-веса для синхронного ранжирования баннеров на клиенте.

        Returns:
            dict[str, object]: Структурированные данные для API или LLM.
        """
        return {
            "version": self._version,
            "product_weights": {
                product_id: {"intercept": value.intercept, "weights": dict(value.weights)}
                for product_id, value in self._product_weights.items()
            },
            "reasons": REASONS,
        }


def _features(profile: BusinessProfile) -> dict[str, float]:
    """Строит признаки для модели рекомендаций.

    Args:
        profile: Профиль клиента или бизнеса.

    Returns:
        dict[str, float]: Числовые признаки или оценки по имени.
    """
    return {
        "legal_form_ooo": float(profile.legal_form == "ooo"),
        "business_age_months": profile.business_age_months / 180,
        "monthly_turnover": min(profile.monthly_turnover, 20_000_000) / 20_000_000,
        "monthly_payment_count": min(profile.monthly_payment_count, 400) / 400,
        "online_sales_share": profile.online_sales_share,
        "has_business_account": float(profile.has_business_account),
        "has_website": float(profile.has_website),
        "has_offline_point": float(profile.has_offline_point),
        "sells_on_marketplaces": float(profile.sells_on_marketplaces),
        "employee_count": min(profile.employee_count, 80) / 80,
        "has_foreign_trade": float(profile.has_foreign_trade),
        "needs_tax_reporting": float(profile.needs_tax_reporting),
        "uses_electronic_documents": float(profile.uses_electronic_documents),
        "wants_business_registration": float(profile.wants_business_registration),
    }


def _applicable(product_id: str, profile: BusinessProfile) -> bool:
    """Отсекает баннеры, для которых в профиле нет базового сценария.

    Args:
        product_id: Идентификатор некредитного продукта.
        profile: Проверенный профиль бизнеса.

    Returns:
        bool: Продукт применим к известному сценарию клиента.
    """
    if product_id == "business_account":
        return not profile.has_business_account
    if product_id == "payroll_project":
        return profile.employee_count > 0
    if product_id == "ved":
        return profile.has_foreign_trade
    if product_id == "marketplace_services":
        return profile.sells_on_marketplaces
    if product_id == "business_registration":
        return profile.wants_business_registration
    if product_id in {"merchant_acquiring", "alfa_kassa", "alfapos"}:
        return profile.has_offline_point
    if product_id == "internet_acquiring":
        return profile.has_website or profile.online_sales_share > 0
    return True


def _score(features: Mapping[str, float], weights: ProductWeights) -> float:
    """Вычисляет оценку продукта по весам.

    Args:
        features: Числовые признаки модели.
        weights: Веса признаков модели.

    Returns:
        float: Вычисленное числовое значение.
    """
    logit = weights.intercept + sum(weights.weights[name] * value for name, value in features.items())
    return 1.0 / (1.0 + math.exp(-logit))


def _validate(profile: BusinessProfile, top_n: int) -> None:
    """Проверяет ограничения доменного контракта.

    Args:
        profile: Профиль клиента или бизнеса.
        top_n: Максимальное число вариантов.

    Raises:
        ValueError: Входные данные нарушают ограничения домена.
    """
    if profile.legal_form not in LEGAL_FORMS:
        raise ValueError("legal_form должен быть ip или ooo.")
    if not 1 <= top_n <= len(NON_CREDIT_PRODUCT_IDS):
        raise ValueError("top_n должен быть от 1 до количества некредитных продуктов.")
    if profile.business_age_months < 0 or profile.monthly_turnover < 0:
        raise ValueError("Возраст бизнеса и оборот не могут быть отрицательными.")
    if profile.monthly_payment_count < 0 or profile.employee_count < 0:
        raise ValueError("Количество платежей и сотрудников не может быть отрицательным.")
    if not 0 <= profile.online_sales_share <= 1:
        raise ValueError("online_sales_share должен быть в диапазоне 0..1.")
    unknown_ids = set(profile.existing_product_ids) - set(NON_CREDIT_PRODUCT_IDS)
    if unknown_ids:
        raise ValueError("existing_product_ids содержит ID вне некредитного каталога.")
