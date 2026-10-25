"""Публичные типы входа и выхода демонстрационного скоринга."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScoringInput:
    """Параметры заявки и синтетического профиля бизнеса.

    Attributes:
        product_id: Идентификатор кредитного продукта.
        requested_amount: Запрошенная сумма кредита.
        term_months: Срок кредита в месяцах.
        business_age_months: Возраст бизнеса в месяцах.
        monthly_revenue: Месячная выручка.
        net_margin_percent: Чистая маржа в процентах.
        debt_to_revenue_ratio: Отношение долга к выручке.
        has_overdue_debt: Признак просроченного долга.
        credit_history_score: Оценка кредитной истории.
        has_collateral: Наличие залога.
        legal_form: Организационно-правовая форма.
    """

    product_id: str
    requested_amount: int
    term_months: int
    business_age_months: int
    monthly_revenue: int
    net_margin_percent: float
    debt_to_revenue_ratio: float
    has_overdue_debt: bool
    credit_history_score: int
    has_collateral: bool
    legal_form: str


@dataclass(frozen=True, slots=True)
class FactorContribution:
    """Вклад одного признака в логит риска.

    Attributes:
        feature: Название признака модели.
        contribution: Вклад фактора в логит риска.
    """

    feature: str
    contribution: float


@dataclass(frozen=True, slots=True)
class ScoringResult:
    """Результат модели, не являющийся кредитным решением.

    Attributes:
        risk_probability: Предварительная вероятность риска.
        risk_band: Категория риска.
        factors: Вклады факторов модели.
        model_version: Версия модели скоринга.
    """

    risk_probability: float
    risk_band: str
    factors: tuple[FactorContribution, ...]
    model_version: str
