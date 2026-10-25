"""Проверки NBA-reranker и его продуктовых границ."""

from dataclasses import replace

from nba import BusinessProfile, NbaEngine


def _profile(**changes: object) -> BusinessProfile:
    values: dict[str, object] = {
        "legal_form": "ip",
        "business_age_months": 12,
        "monthly_turnover": 1_200_000,
        "monthly_payment_count": 60,
        "online_sales_share": 0.7,
        "has_business_account": True,
        "has_website": True,
        "has_offline_point": False,
        "sells_on_marketplaces": True,
        "employee_count": 2,
        "has_foreign_trade": False,
        "needs_tax_reporting": True,
        "uses_electronic_documents": False,
        "wants_business_registration": False,
        "existing_product_ids": ("business_account",),
    }
    values.update(changes)
    return BusinessProfile(**values)


def test_nba_returns_requested_number_of_unique_non_credit_ids() -> None:
    recommendations = NbaEngine.from_json().recommend(_profile(), top_n=3)
    assert len(recommendations) == 3
    assert len({item.product_id for item in recommendations}) == 3
    assert all(item.product_id != "business_account" for item in recommendations)


def test_online_business_prioritizes_internet_acquiring() -> None:
    recommendations = NbaEngine.from_json().recommend(_profile(), top_n=5)
    assert "internet_acquiring" in {item.product_id for item in recommendations}


def test_banners_follow_business_scenario_and_exclude_irrelevant_services() -> None:
    """Контрастные профили дают разные первые баннеры по реальной потребности."""
    engine = NbaEngine.from_json()
    base = _profile(
        online_sales_share=0,
        has_website=False,
        sells_on_marketplaces=False,
        employee_count=0,
        needs_tax_reporting=False,
    )
    scenarios = {
        "new": (replace(base, wants_business_registration=True, has_business_account=False), "business_registration"),
        "online": (replace(base, online_sales_share=1, has_website=True), "internet_acquiring"),
        "offline": (replace(base, has_offline_point=True), "merchant_acquiring"),
        "marketplace": (replace(base, sells_on_marketplaces=True), "marketplace_services"),
        "export": (replace(base, has_foreign_trade=True), "ved"),
    }
    first_products = set()
    for profile, expected in scenarios.values():
        recommendations = engine.recommend(profile, top_n=3)
        product_ids = {item.product_id for item in recommendations}
        assert expected in product_ids
        assert "payroll_project" not in product_ids
        first_products.add(recommendations[0].product_id)
    assert len(first_products) >= 4


def test_existing_and_inapplicable_products_do_not_appear_in_banners() -> None:
    """Профиль без сотрудников и ВЭД не получает связанные с ними баннеры."""
    engine = NbaEngine.from_json()
    profile = _profile(
        employee_count=0,
        has_foreign_trade=False,
        sells_on_marketplaces=False,
        has_offline_point=False,
        wants_business_registration=False,
        existing_product_ids=("business_account", "business_card"),
    )
    product_ids = {item.product_id for item in engine.recommend(profile, top_n=18)}
    assert not product_ids & {
        "business_account",
        "business_card",
        "payroll_project",
        "ved",
        "marketplace_services",
        "merchant_acquiring",
        "alfa_kassa",
        "alfapos",
        "business_registration",
    }
