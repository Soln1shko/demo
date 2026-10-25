"""Контракт профиля бизнеса и результата next-best-action."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BusinessProfile:
    """Минимальный набор фактов для рекомендации сервисов МСБ.

    Attributes:
        legal_form: Организационно-правовая форма.
        business_age_months: Возраст бизнеса в месяцах.
        monthly_turnover: Месячный оборот.
        monthly_payment_count: Число платежей в месяц.
        online_sales_share: Доля онлайн-продаж.
        has_business_account: Наличие расчётного счёта.
        has_website: Наличие сайта.
        has_offline_point: Наличие офлайн-точки.
        sells_on_marketplaces: Признак продаж на маркетплейсах.
        employee_count: Количество сотрудников.
        has_foreign_trade: Наличие внешнеэкономической деятельности.
        needs_tax_reporting: Потребность в налоговой отчётности.
        uses_electronic_documents: Признак электронного документооборота.
        wants_business_registration: Запрос регистрации бизнеса.
        existing_product_ids: Идентификаторы уже подключённых продуктов.
    """

    legal_form: str
    business_age_months: int
    monthly_turnover: int
    monthly_payment_count: int
    online_sales_share: float
    has_business_account: bool
    has_website: bool
    has_offline_point: bool
    sells_on_marketplaces: bool
    employee_count: int
    has_foreign_trade: bool
    needs_tax_reporting: bool
    uses_electronic_documents: bool
    wants_business_registration: bool
    existing_product_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Один продукт для баннера в профиле предпринимателя.

    Attributes:
        product_id: Идентификатор некредитного продукта.
        score: Оценка релевантности или риска.
        reason: Обоснование оценки или действия.
    """

    product_id: str
    score: float
    reason: str
