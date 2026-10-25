"""Справочники продуктов из CSV (`backend/app/data/*.csv`).

Идентификаторы `product_id` в CSV общие с ML-командой: в БД продукты лежат под теми же id.
Файлы — копии `data/*.csv` из корня репозитория (тест следит, чтобы они не разошлись).
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CREDIT_CSV = DATA_DIR / "credit_products.csv"
SERVICE_CSV = DATA_DIR / "service_products.csv"
PROFITS_URL = "https://alfabank.ru/sme/profits/"

# Старые id → id из справочника. Нужны, чтобы существующие БД (заявки, черновики) переехали без потерь.
# Варианты «с залогом / невозобновляемая линия» в справочнике отдельными продуктами не существуют.
LEGACY_IDS = {
    "working": "business_loan",
    "equipment": "business_loan",
    "line": "credit_line",
    "line-secured": "credit_line",
    "nonrev": "credit_line",
    "alfastart": "alfa_start",
    "lombard": "business_pledge_loan",
    "mortgage": "business_mortgage",
}

# Продукты из справочника, для которых у нас нет ставок: показываем в БД, но не считаем платёж.
# Тексты — без цифр, чтобы не придумывать условия банка.
CATALOG_ONLY: dict[str, dict[str, Any]] = {
    "business_auto_loan": dict(
        short="Транспорт и спецтехника",
        category="investment",
        desc="Покупка автомобиля или спецтехники для бизнеса. Транспорт остаётся в залоге.",
    ),
    "seller_credit": dict(
        short="Оборотка для маркетплейсов",
        category="working",
        desc="Возобновляемая линия для продавцов на маркетплейсах. Нужны продажи на площадке.",
    ),
    "business_refinancing": dict(
        short="Перекредитование",
        category="working",
        desc="Объединение действующих кредитов бизнеса на новых условиях.",
    ),
    "business_credit_card": dict(
        short="Короткие расходы",
        category="gap",
        desc="Кредитная карта для текущих расходов компании с льготным периодом.",
    ),
    "partner_installment": dict(
        short="Покупка у партнёров банка",
        category="working",
        desc="Кредит или рассрочка на покупку у партнёров. Условия задаёт партнёр.",
    ),
}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _tags(value: str) -> list[str]:
    return [t for t in value.split(";") if t]


def _bool(value: str) -> bool:
    return value.strip().lower() == "true"


@lru_cache
def credit_rows() -> list[dict[str, Any]]:
    out = []
    for r in _read(CREDIT_CSV):
        out.append({
            "id": r["product_id"], "name": r["product_name"], "segment": r["segment"], "family": r["product_family"],
            "purpose_tags": _tags(r["purpose_tags"]), "pricing_type": r["pricing_type"],
            "collateral_policy": r["collateral_policy"], "new_business_allowed": _bool(r["new_business_allowed"]),
            "marketplace_required": _bool(r["marketplace_required"]), "effective_at": r["effective_at"],
            "min_amount": float(r["min_amount_rub"]), "max_amount": float(r["max_amount_rub"]),
            "min_months": int(r["min_term_months"]), "max_months": int(r["max_term_months"]),
            "source_url": r["source_url"],
        })  # fmt: skip
    return out


@lru_cache
def service_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": r["product_id"],
            "name": r["product_name"],
            "segment": r["segment"],
            "family": r["product_family"],
            "purpose_tags": _tags(r["purpose_tags"]),
            "eligibility_tags": _tags(r["eligibility_tags"]),
            "source_url": r["source_url"],
            "effective_at": r["effective_at"],
        }  # fmt: skip
        for r in _read(SERVICE_CSV)
    ]


def relative_source(url: str) -> str:
    """Путь внутри /sme/profits/ — так хранит source_url каталог кабинета."""
    return url.removeprefix(PROFITS_URL) if url.startswith(PROFITS_URL) else ""
