"""Признаки модели, вычисляемые только по сгенерированной истории операций."""

from statistics import pstdev

from cash_cap.schema import BankDay


def extract_features(history: tuple[BankDay, ...]) -> dict[str, float]:
    """Сводит историю в устойчивые показатели ликвидности и волатильности.

    Args:
        history: История переписки.

    Returns:
        dict[str, float]: Числовые признаки или оценки по имени.

    Raises:
        ValueError: Входные данные нарушают ограничения домена.
    """
    if not history:
        raise ValueError("Для прогноза нужна непустая банковская история.")
    inflows = [item.inflow for item in history]
    outflows = [item.outflow for item in history]
    balances = [item.closing_balance for item in history]
    average_inflow = sum(inflows) / len(inflows)
    average_outflow = sum(outflows) / len(outflows)
    return {
        "current_balance_to_outflow": balances[-1] / max(average_outflow, 1),
        "net_cash_flow_ratio": (average_inflow - average_outflow) / max(average_inflow, 1),
        "outflow_volatility": pstdev(outflows) / max(average_outflow, 1),
        "minimum_balance_to_outflow": min(balances) / max(average_outflow, 1),
        "negative_balance_days_share": sum(balance < 0 for balance in balances) / len(balances),
    }
