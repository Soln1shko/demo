"""Контракты профиля, банковской синтетики и прогноза."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CashProfile:
    """Обезличенные параметры бизнеса для локальной симуляции операций.

    Attributes:
        monthly_revenue: Месячная выручка.
        net_margin_percent: Чистая маржа в процентах.
        opening_balance: Начальный остаток средств.
        monthly_fixed_costs: Месячные постоянные расходы.
        sales_volatility: Волатильность продаж.
        payment_delay_days: Задержка платежей в днях.
        upcoming_expenses: Предстоящие расходы.
        simulation_seed: Seed воспроизводимой симуляции.
    """

    monthly_revenue: int
    net_margin_percent: float
    opening_balance: int
    monthly_fixed_costs: int
    sales_volatility: float
    payment_delay_days: int
    upcoming_expenses: int = 0
    simulation_seed: int = 20261022


@dataclass(frozen=True, slots=True)
class BankDay:
    """Синтетический дневной срез движений расчётного счёта.

    Attributes:
        day: Номер дня прогноза.
        inflow: Поступления за день.
        outflow: Списания за день.
        closing_balance: Остаток на конец дня.
    """

    day: int
    inflow: int
    outflow: int
    closing_balance: int


@dataclass(frozen=True, slots=True)
class CashGapForecast:
    """Предварительный прогноз разрыва на заданный горизонт.

    Attributes:
        cash_gap_probability: Вероятность кассового разрыва.
        risk_band: Категория риска.
        estimated_shortfall: Оценка дефицита средств.
        forecast_days: Горизонт прогноза.
        factors: Вклады факторов модели.
    """

    cash_gap_probability: float
    risk_band: str
    estimated_shortfall: int
    forecast_days: int
    factors: tuple[str, ...]
