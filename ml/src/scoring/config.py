"""Конфигурация демонстрационного скоринга."""

from pathlib import Path

PRODUCT_IDS = (
    "business_loan",
    "credit_line",
    "alfa_start",
    "business_pledge_loan",
    "business_mortgage",
    "business_auto_loan",
    "overdraft",
    "seller_credit",
    "business_refinancing",
    "business_credit_card",
    "partner_installment",
)
LEGAL_FORMS = ("ip", "ooo")
MODEL_PATH = Path(__file__).with_name("model_weights.json")
