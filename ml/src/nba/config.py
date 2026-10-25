"""Конфигурация каталога и модели next-best-action."""

from pathlib import Path

NON_CREDIT_PRODUCT_IDS = (
    "business_account",
    "rko_zero",
    "rko_simple",
    "rko_fast_growth",
    "rko_active",
    "business_online",
    "business_card",
    "merchant_acquiring",
    "internet_acquiring",
    "sbp_business",
    "alfa_kassa",
    "alfapos",
    "payroll_project",
    "ved",
    "business_accounting",
    "marketplace_services",
    "business_registration",
    "electronic_signature",
)
LEGAL_FORMS = ("ip", "ooo")
MODEL_PATH = Path(__file__).with_name("model_weights.json")

REASONS = {
    "business_account": "Для регулярных расчётов с контрагентами.",
    "rko_zero": "Подходит новому бизнесу с небольшим числом операций.",
    "rko_simple": "Подходит небольшому бизнесу со стабильными расчётами.",
    "rko_fast_growth": "Подходит растущему бизнесу с регулярными платежами.",
    "rko_active": "Подходит при высокой платёжной активности.",
    "business_online": "Упростит платежи, документы и доступы сотрудникам.",
    "business_card": "Для расходов бизнеса и корпоративных платежей.",
    "merchant_acquiring": "Для приёма оплат в офлайн-точке.",
    "internet_acquiring": "Для приёма онлайн-оплаты на сайте и по ссылке.",
    "sbp_business": "Для оплаты по QR в онлайне и офлайне.",
    "alfa_kassa": "Для кассовых чеков при приёме оплаты.",
    "alfapos": "Для приёма оплаты смартфоном или мобильным терминалом.",
    "payroll_project": "Для регулярных выплат сотрудникам.",
    "ved": "Для валютных операций и международных расчётов.",
    "business_accounting": "Для учёта, налогов и отчётности.",
    "marketplace_services": "Для расчётов и сервисов продавца маркетплейсов.",
    "business_registration": "Для запуска нового бизнеса.",
    "electronic_signature": "Для подписания документов и отчётности.",
}
