"""Справочники продуктов и движки используют одни и те же product_id."""

import csv
from pathlib import Path

from credit_advisor.config import PRODUCT_RULES
from nba import NbaEngine
from nba.config import NON_CREDIT_PRODUCT_IDS
from scoring import ScoringEngine
from scoring.config import PRODUCT_IDS

DATA = Path(__file__).parents[1] / "data"


def _ids(filename: str) -> set[str]:
    with (DATA / filename).open(encoding="utf-8", newline="") as source:
        return {row["product_id"] for row in csv.DictReader(source)}


def test_scoring_product_ids_exist_in_credit_catalog() -> None:
    catalog_ids = _ids("credit_products.csv")
    scoring_ids = set(ScoringEngine.from_json().browser_payload()["categorical_weights"]["product_id"])
    assert set(PRODUCT_IDS) == catalog_ids
    assert scoring_ids == catalog_ids


def test_credit_advisor_rules_are_loaded_from_credit_catalog() -> None:
    """Суммы, сроки и цели не дублируются в Python-конфиге."""
    with (DATA / "credit_products.csv").open(encoding="utf-8", newline="") as source:
        rows = {row["product_id"]: row for row in csv.DictReader(source)}
    for product_id, rule in PRODUCT_RULES.items():
        row = rows[product_id]
        assert rule.min_amount == int(row["min_amount_rub"])
        assert rule.max_amount == int(row["max_amount_rub"])
        assert rule.min_term_months == int(row["min_term_months"])
        assert rule.max_term_months == int(row["max_term_months"])
        assert rule.requires_purpose == (row["requires_purpose"] or None)


def test_nba_product_ids_and_weights_exist_in_non_credit_catalog() -> None:
    catalog_ids = _ids("service_products.csv")
    engine_ids = set(NbaEngine.from_json().browser_payload()["product_weights"])
    assert set(NON_CREDIT_PRODUCT_IDS) <= catalog_ids
    assert engine_ids == set(NON_CREDIT_PRODUCT_IDS)
