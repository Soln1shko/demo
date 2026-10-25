"""Конфигурация подбора: кредитный CSV — единственный источник условий."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from scoring.config import PRODUCT_IDS

DATA = Path(__file__).parents[2] / "data"
CREDIT_CATALOG = DATA / "credit_products.csv"


@dataclass(frozen=True, slots=True)
class ProductRule:
    """Условия предварительной фильтрации одного кредитного продукта.

    Attributes:
        min_amount: Минимальная сумма продукта.
        max_amount: Максимальная сумма продукта.
        min_term_months: Минимальный срок кредита.
        max_term_months: Максимальный срок кредита.
        min_business_age_months: Минимальный возраст бизнеса.
        requires_collateral: Требование залога.
        requires_marketplace_sales: Требование продаж на маркетплейсах.
        requires_existing_loans: Требование действующего кредита.
        requires_purpose: Допустимая цель кредита.
        context_tags: Метки потребностей бизнеса.
    """

    min_amount: int
    max_amount: int
    min_term_months: int
    max_term_months: int
    min_business_age_months: int
    requires_collateral: bool = False
    requires_marketplace_sales: bool = False
    requires_existing_loans: bool = False
    requires_purpose: str | None = None
    context_tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RankingConfig:
    """Веса детерминированной оценки до LLM-ранжирования.

    Attributes:
        approval_probability_weight: Вес оценки одобрения при ранжировании.
        context_relevance_weight: Вес соответствия продукта контексту.
    """

    approval_probability_weight: float = 0.6
    context_relevance_weight: float = 0.4


def load_product_rules(path: Path = CREDIT_CATALOG) -> dict[str, ProductRule]:
    """Строит продуктовые правила из версионируемого CSV-каталога.

    Args:
        path: Путь к полю или файлу.

    Returns:
        dict[str, ProductRule]: Правила кредитных продуктов по ID.

    Raises:
        RuntimeError: Операция завершилась ошибкой.
    """
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    rules = {
        row["product_id"]: ProductRule(
            min_amount=int(row["min_amount_rub"]),
            max_amount=int(row["max_amount_rub"]),
            min_term_months=int(row["min_term_months"]),
            max_term_months=int(row["max_term_months"]),
            min_business_age_months=int(row["min_business_age_months"]),
            requires_collateral=row["collateral_policy"] == "required",
            requires_marketplace_sales=_as_bool(row["marketplace_required"]),
            requires_existing_loans=_as_bool(row["requires_existing_loans"]),
            requires_purpose=row["requires_purpose"] or None,
            context_tags=tuple(tag for tag in row["purpose_tags"].split(";") if tag),
        )
        for row in rows
    }
    if set(rules) != set(PRODUCT_IDS):
        raise RuntimeError("Кредитный CSV и scoring.config.PRODUCT_IDS расходятся.")
    return rules


def _as_bool(value: str) -> bool:
    """Преобразует значение каталога в булев признак.

    Args:
        value: Значение факта или признака.

    Returns:
        bool: Результат проверки условия.

    Raises:
        ValueError: Входные данные нарушают ограничения домена.
    """
    if value not in {"true", "false"}:
        raise ValueError(f"Ожидалось true или false в кредитном CSV, получено: {value!r}.")
    return value == "true"


PRODUCT_RULES = load_product_rules()
RANKING = RankingConfig()
