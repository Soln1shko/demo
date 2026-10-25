# Демонстрационный скоринг

`ScoringEngine` оценивает **риск** выбранного кредита и показывает вклад параметров. Он не одобряет заявку и не определяет ставку или кредитный лимит. Модель — объяснимый baseline с локальными JSON-весами; реальные клиентские данные для разработки не используются.

## Вход и результат

`POST /v1/scoring` принимает `product_id` кредитного каталога, сумму и срок, возраст бизнеса, месячную выручку, чистую маржу, отношение долга к выручке, признак просрочки, синтетическую оценку кредитной истории, залог и `legal_form: ip|ooo`. Диапазоны и обязательность полей описаны в [HTTP-контракте](../../docs/architecture/HTTP-API.md).

Ответ:

| Поле | Значение |
| --- | --- |
| `risk_probability` | Результат логистической функции от взвешенных признаков, число от 0 до 1 |
| `risk_band` | Демонстрационная группа риска по порогам JSON-модели |
| `factors[]` | Три максимальных по модулю вклада (`feature`, `contribution`); положительный вклад повышает логит риска |
| `model_version` | Версия загруженных весов |

## Расчёт

`model_weights.json` хранит `intercept`, средние и масштабы числовых признаков, числовые и категориальные веса, пороги групп риска. Для числового признака вклад равен `(value - mean) / scale * weight`; категориальные вклады добавляются по `product_id` и `legal_form`. Итоговая вероятность — сигмоида суммы вкладов. `ScoringEngine.from_json()` загружает веса один раз, `score()` затем не делает I/O.

```python
from scoring import ScoringEngine, ScoringInput

engine = ScoringEngine.from_json()
result = engine.score(
    ScoringInput(
        product_id="business_loan",
        requested_amount=2000000,
        term_months=36,
        business_age_months=28,
        monthly_revenue=1500000,
        net_margin_percent=18,
        debt_to_revenue_ratio=0.8,
        has_overdue_debt=False,
        credit_history_score=720,
        has_collateral=False,
        legal_form="ip",
    )
)
print(result.risk_probability, result.factors)
```

Метод `browser_payload()` возвращает те же веса в JSON-совместимом виде для будущего калькулятора без запроса на каждое движение ползунка. Готового браузерного калькулятора в репозитории нет; бэк может повторить расчёт Python-движком при отправке заявки.

## Ограничения и проверка

Допустимые `product_id` сверяются с кредитным CSV; отрицательные показатели, неизвестная форма бизнеса или значение вне диапазона дают `422` через HTTP. Веса и пороги демонстрационные; `1 - risk_probability` нельзя выдавать за калиброванный шанс одобрения. Проверка: `uv run pytest -q tests/test_scoring.py tests/test_catalog_ids.py tests/test_api.py`.
