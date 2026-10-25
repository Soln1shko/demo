# Альтернативные условия после отказа

`POST /v1/offer-recovery/recommendations` ищет меньшую сумму, более короткий срок или другой ранее рекомендованный кредитный продукт. Расчёт идёт в памяти через тот же `ScoringEngine`, без HTTP-вызова `/v1/scoring` и без OpenRouter.

## Контракт

Вход содержит `case_id`, полный `profile` по схеме Credit Advisor, непустой список `declined_offers[]` с продуктом, суммой, сроком и причинами отказа; непустые уникальные `recommended_product_ids[]`; `minimum_acceptable_amount` и `minimum_acceptable_term_months`. Минимально приемлемые значения не могут превышать исходные. Список продуктов должен содержать только кредитные ID из каталога.

```json
{
  "case_id": "DEMO-001",
  "profile": {
    "requested_amount": 2000000, "term_months": 36, "purpose": "working_capital",
    "business_age_months": 24, "monthly_revenue": 800000,
    "net_margin_percent": 12, "debt_to_revenue_ratio": 0.8,
    "has_overdue_debt": false, "credit_history_score": 700,
    "has_collateral": false, "legal_form": "ip",
    "has_marketplace_sales": false, "has_existing_business_loans": false
  },
  "declined_offers": [{
    "product_id": "business_loan", "requested_amount": 2000000,
    "term_months": 36, "reasons": ["Высокая долговая нагрузка."]
  }],
  "recommended_product_ids": ["business_loan"],
  "minimum_acceptable_amount": 800000,
  "minimum_acceptable_term_months": 12
}
```

## Алгоритм

1. Последний отказ задаёт базовую вероятность риска. Причины отказов сохраняются как текст, но не превращаются в банковские правила без структурированных кодов.
2. Для каждого рекомендованного продукта конфигурация задаёт ограниченный набор долей суммы `(1.0, 0.9, 0.75, 0.5)` и срока `(1.0, 0.75, 0.5)`. Значения ограничиваются минимально приемлемыми условиями и диапазоном продукта.
3. Отклонённые сочетания исключаются. Продуктовые правила проверяются до скоринга. Вариант остаётся, только если модельный риск снизился хотя бы на `0.01` относительно последнего отказа.
4. Для каждого продукта возвращаются максимум два варианта: с наименьшим риском и ближайший к исходным сумме и сроку. Если подходящих нет, продукт попадает в `unavailable_products` с причиной.

Ответ: `variants[]` (`suggested_terms`, `risk_probability`, `risk_band`, `risk_change_vs_original`, `explanation`, версия модели), `unavailable_products[]`, `declined_reasons[]`, `estimate_type: synthetic_risk_probability`. Отрицательное изменение риска означает снижение **оценки риска**, не вероятность одобрения. Профиль и остальные факты не подменяются ради лучшего результата.

## Проверка

Маршрут работает без ключа OpenRouter. Неизвестный `product_id` и нарушения входного контракта дают `422`. `uv run pytest -q tests/test_offer_recovery.py tests/test_api.py` проверяет альтернативы, исключения и HTTP-сценарий. Условия CSV демонстрационные; актуальная индивидуальная оферта может отличаться.

[HTTP-контракт](../../docs/architecture/HTTP-API.md) · [Кредитный советник](../credit_advisor/README.md)
