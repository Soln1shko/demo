"""Генерация синтетической банковской истории из параметров бизнеса."""

from __future__ import annotations

import random

from cash_cap.schema import BankDay, CashProfile


def generate_bank_data(profile: CashProfile, days: int, seed: int | None = None) -> tuple[BankDay, ...]:
    """Создаёт детерминированные поступления и списания без реальных операций.

    Args:
        profile: Профиль клиента или бизнеса.
        days: Количество дней.
        seed: Seed генерации.

    Returns:
        tuple[BankDay, ...]: Синтетическая история банковских операций.
    """
    _validate(profile, days)
    randomizer = random.Random(profile.simulation_seed if seed is None else seed)
    balance = profile.opening_balance
    history: list[BankDay] = []
    margin = profile.net_margin_percent / 100
    for day in range(1, days + 1):
        seasonal_factor = 1 + 0.12 * ((day % 14) / 14 - 0.5)
        inflow_noise = randomizer.uniform(-profile.sales_volatility, profile.sales_volatility)
        inflow = max(0, round(profile.monthly_revenue / 30 * seasonal_factor * (1 + inflow_noise)))
        variable_outflow = inflow * (1 - margin)
        fixed_outflow = profile.monthly_fixed_costs / 30
        outflow_noise = randomizer.uniform(0.94, 1.08)
        outflow = max(0, round((variable_outflow + fixed_outflow) * outflow_noise))
        if profile.upcoming_expenses and day % 30 == min(30, max(1, profile.payment_delay_days + 7)):
            outflow += profile.upcoming_expenses
        balance += inflow - outflow
        history.append(BankDay(day=day, inflow=inflow, outflow=outflow, closing_balance=balance))
    return tuple(history)


def _validate(profile: CashProfile, days: int) -> None:
    """Проверяет ограничения доменного контракта.

    Args:
        profile: Профиль клиента или бизнеса.
        days: Количество дней.

    Raises:
        ValueError: Входные данные нарушают ограничения домена.
    """
    if days < 1:
        raise ValueError("Количество дней должно быть положительным.")
    if profile.monthly_revenue < 0 or profile.opening_balance < 0:
        raise ValueError("Выручка и начальный остаток не могут быть отрицательными.")
    if profile.monthly_fixed_costs < 0 or profile.upcoming_expenses < 0:
        raise ValueError("Расходы не могут быть отрицательными.")
    if not 0 <= profile.net_margin_percent <= 100:
        raise ValueError("net_margin_percent должен быть в диапазоне 0..100.")
    if not 0 <= profile.sales_volatility <= 1:
        raise ValueError("sales_volatility должен быть в диапазоне 0..1.")
    if profile.payment_delay_days < 0:
        raise ValueError("payment_delay_days не может быть отрицательным.")
