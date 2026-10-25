"""Типизированные допущения демонстрационной финансовой модели."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FinancialConfig:
    """Границы прогноза, стресс-теста и поиска допустимых действий.

    Attributes:
        trend_limit: Максимальный месячный тренд выручки.
        minimum_volatility: Нижняя граница месячной неопределённости.
        maximum_volatility: Верхняя граница месячной неопределённости.
        uncertainty_multiplier: Множитель иллюстративного интервала.
        maximum_uncertainty_fraction: Верхняя граница относительного интервала.
        fixed_expense_share: Доля расходов, сохраняющаяся без выручки.
        annual_growth_min: Нижняя граница годового множителя выручки.
        annual_growth_max: Верхняя граница годового множителя выручки.
        stress_revenue_multiplier: Доля выручки в стрессовом сценарии.
        optimistic_revenue_multiplier: Доля выручки в оптимистичном сценарии.
        stress_expense_multiplier: Множитель расходов в стрессовом сценарии.
        minimum_cash_reserve_months: Минимальный резерв после погашения долга.
        quest_amount_fractions: Проверяемые доли суммы заявки.
        quest_expense_fractions: Проверяемые доли снижения расходов.
        quest_debt_fractions: Проверяемые доли погашения старого долга.
    """

    trend_limit: float = 0.04
    minimum_volatility: float = 0.05
    maximum_volatility: float = 0.3
    uncertainty_multiplier: float = 1.28
    maximum_uncertainty_fraction: float = 0.8
    fixed_expense_share: float = 0.5
    annual_growth_min: float = 0.7
    annual_growth_max: float = 1.3
    stress_revenue_multiplier: float = 0.8
    optimistic_revenue_multiplier: float = 1.1
    stress_expense_multiplier: float = 1.05
    minimum_cash_reserve_months: float = 1.0
    quest_amount_fractions: tuple[float, ...] = (0.9, 0.75, 0.5)
    quest_expense_fractions: tuple[float, ...] = (0.05, 0.1)
    quest_debt_fractions: tuple[float, ...] = (0.25, 0.5)


CONFIG = FinancialConfig()
