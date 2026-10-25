"""Прозрачный прогноз денежных показателей по синтетической истории."""

from __future__ import annotations

from datetime import date
from statistics import mean, pstdev

from financial_intelligence.config import CONFIG, FinancialConfig
from financial_intelligence.schema import ForecastMonth, ForecastRequest, ForecastResponse


def add_months(month: date, count: int) -> date:
    """Сдвигает первый день месяца.

    Args:
        month: Первый день исходного месяца.
        count: Число месяцев сдвига.

    Returns:
        date: Первый день целевого месяца.
    """
    index = month.year * 12 + month.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


def forecast_financials(request: ForecastRequest, config: FinancialConfig = CONFIG) -> ForecastResponse:
    """Прогнозирует поступления и расходы без эффекта будущего кредита.

    Args:
        request: История и горизонт прогноза.
        config: Пороговые допущения baseline.

    Returns:
        ForecastResponse: Центральный прогноз и иллюстративный диапазон.
    """
    history = request.history
    recent = history[-min(6, len(history)) :]
    revenue_base = mean(item.revenue for item in recent)
    revenue_total = sum(item.revenue for item in recent)
    expense_base = mean(item.operating_expenses for item in recent)
    fixed_expenses = expense_base * config.fixed_expense_share if revenue_total else expense_base
    variable_expense_ratio = (
        (sum(item.operating_expenses for item in recent) - fixed_expenses * len(recent)) / revenue_total
        if revenue_total
        else 0.0
    )
    tax_ratio = sum(item.taxes for item in recent) / revenue_total if revenue_total else 0.0
    fixed_taxes = mean(item.taxes for item in recent) if not revenue_total else 0.0
    debt_payment = round(mean(item.existing_debt_payment for item in recent))
    half = max(3, len(history) // 2)
    earlier = mean(item.revenue for item in history[-2 * half : -half])
    later = mean(item.revenue for item in history[-half:])
    raw_trend = (later / max(earlier, 1)) ** (1 / half) - 1 if earlier else 0.0
    trend = max(-config.trend_limit, min(config.trend_limit, raw_trend))
    changes = [
        history[index].revenue / max(history[index - 1].revenue, 1) - 1
        for index in range(1, len(history))
        if history[index - 1].revenue > 0
    ]
    volatility = max(config.minimum_volatility, min(config.maximum_volatility, pstdev(changes) if changes else 0))
    seasonal: dict[int, int] = {}
    annual_factor = 1.0
    if len(history) >= 18:
        seasonal = {item.month.month: item.revenue for item in history[-12:]}
        comparison = min(12, len(history) - 12)
        current_year = mean(item.revenue for item in history[-comparison:])
        previous_year = mean(item.revenue for item in history[-comparison - 12 : -12])
        annual_factor = max(
            config.annual_growth_min,
            min(config.annual_growth_max, current_year / max(previous_year, 1)),
        )
    months: list[ForecastMonth] = []
    for step in range(1, request.horizon_months + 1):
        month = add_months(history[-1].month, step)
        revenue = round(
            seasonal[month.month] * annual_factor if month.month in seasonal else revenue_base * (1 + trend) ** step
        )
        expenses = round(fixed_expenses + revenue * variable_expense_ratio)
        spread = min(config.maximum_uncertainty_fraction, volatility * config.uncertainty_multiplier * step**0.5)
        months.append(
            ForecastMonth(
                month=month,
                revenue=revenue,
                revenue_low=max(0, round(revenue * (1 - spread))),
                revenue_high=round(revenue * (1 + spread)),
                operating_expenses=expenses,
                expenses_low=max(0, round(expenses * (1 - spread))),
                expenses_high=round(expenses * (1 + spread)),
                taxes=round(fixed_taxes + revenue * tax_ratio),
                existing_debt_payment=debt_payment,
            )
        )
    return ForecastResponse(company_id=request.company_id, opening_cash=history[-1].cash_balance, months=months)


def rolling_backtest(request: ForecastRequest, holdout_months: int = 6) -> dict[str, float]:
    """Оценивает однократный прогноз на следующих отложенных месяцах.

    Args:
        request: История с не менее чем шестью обучающими месяцами.
        holdout_months: Число последних месяцев для проверки.

    Returns:
        dict[str, float]: WAPE выручки и покрытие эвристического интервала.

    Raises:
        ValueError: Для выбранного отложенного периода мало истории.
    """
    if holdout_months < 1 or len(request.history) - holdout_months < 6:
        raise ValueError("Для backtest нужно минимум шесть обучающих месяцев и один отложенный.")
    absolute_error = 0
    total_revenue = 0
    covered = 0
    for index in range(len(request.history) - holdout_months, len(request.history)):
        training = request.model_copy(update={"history": request.history[:index], "horizon_months": 1})
        estimate = forecast_financials(training).months[0]
        actual = request.history[index].revenue
        absolute_error += abs(estimate.revenue - actual)
        total_revenue += actual
        covered += estimate.revenue_low <= actual <= estimate.revenue_high
    return {
        "revenue_wape": round(absolute_error / max(total_revenue, 1), 4),
        "interval_coverage": round(covered / holdout_months, 4),
    }
