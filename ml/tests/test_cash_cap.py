"""Проверки разделения банковской симуляции и прогноза разрыва."""

from cash_cap import CashGapEngine, CashProfile


def _profile(**changes: object) -> CashProfile:
    values: dict[str, object] = {
        "monthly_revenue": 1500000,
        "net_margin_percent": 18,
        "opening_balance": 500000,
        "monthly_fixed_costs": 300000,
        "sales_volatility": 0.2,
        "payment_delay_days": 7,
        "upcoming_expenses": 0,
        "simulation_seed": 7,
    }
    values.update(changes)
    return CashProfile(**values)


def test_bank_data_is_reproducible_for_same_profile() -> None:
    engine = CashGapEngine.from_json()
    assert engine.generate_bank_data(_profile()) == engine.generate_bank_data(_profile())


def test_large_upcoming_expense_increases_cash_gap_probability() -> None:
    engine = CashGapEngine.from_json()
    safe = engine.predict(_profile())
    stressed = engine.predict(_profile(opening_balance=50000, monthly_fixed_costs=1200000, upcoming_expenses=1000000))
    assert stressed.cash_gap_probability > safe.cash_gap_probability


def test_forecast_contains_non_negative_shortfall() -> None:
    forecast = CashGapEngine.from_json().predict(_profile())
    assert forecast.estimated_shortfall >= 0
    assert forecast.forecast_days == 30
