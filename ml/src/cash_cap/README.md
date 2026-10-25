# Прогноз кассового разрыва

`CashGapEngine` показывает демонстрационный риск дефицита средств. Вход — обезличенные параметры бизнеса, а не реальные банковские операции. История счёта создаётся локальной детерминированной симуляцией.

## Вход и ответ

`POST /v1/cash-gap/forecast` принимает обязательные `monthly_revenue`, `net_margin_percent`, `opening_balance`, `monthly_fixed_costs`, `sales_volatility`, `payment_delay_days`; необязательные `upcoming_expenses=0`, `simulation_seed=20261022`, `forecast_days=30` (1–365). Ответ: `cash_gap_probability`, `risk_band`, `estimated_shortfall`, `forecast_days`, `factors[]`.

`cash_gap_probability` — оценка риска baseline-модели; `estimated_shortfall` — оценка возможного дефицита на выбранный горизонт, а не прогноз реального остатка банка.

## Два шага расчёта

1. `generate_bank_data(profile, days=60)` создаёт дневные поступления, списания и закрывающий остаток. Одинаковый `simulation_seed` даёт воспроизводимую историю.
2. `predict(profile, forecast_days=30)` строит признаки истории и применяет локальные веса из `model_weights.json`. Сетевых запросов или вызовов LLM нет.

```python
from cash_cap import CashGapEngine, CashProfile

profile = CashProfile(
    monthly_revenue=1500000,
    net_margin_percent=15,
    opening_balance=200000,
    monthly_fixed_costs=400000,
    sales_volatility=0.3,
    payment_delay_days=14,
    upcoming_expenses=250000,
    simulation_seed=20261022,
)
engine = CashGapEngine.from_json()
forecast = engine.predict(profile, forecast_days=30)
```

## Ограничения и проверка

Симулятор и веса не обучаются на банковской истории клиента; результат нельзя использовать для финансового решения. Некорректные диапазоны входа дают `422` через HTTP. Проверка: `uv run pytest -q tests/test_cash_cap.py tests/test_api.py`.

[HTTP-контракт](../../docs/architecture/HTTP-API.md)
