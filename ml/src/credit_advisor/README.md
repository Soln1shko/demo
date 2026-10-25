# Предварительный подбор кредита

`CreditAdvisor` проверяет обязательные условия кредитных продуктов, рассчитывает модельный риск для допустимых вариантов и готовит контекст для LLM-ранжирования. Он возвращает рекомендации, а не банковское одобрение.

## Вход и выход

`POST /v1/credit-advisor/recommendations` получает финансовые признаки скоринга без `product_id`, `purpose`, `has_marketplace_sales`, `has_existing_business_loans`; необязательные `context_tags[]` и `top_n` от 1 до 11. Источник продуктовых диапазонов и обязательных признаков — `data/Кредитные-продукты-Альфа-Банка-МСБ.csv`.

Ответ содержит `recommendations[]` с `rank`, `product_id`, `preliminary_approval_probability`, `risk_probability`, `context_relevance`, `combined_score`, `reasons[]` и текстовым `reason`; также `excluded_product_ids[]` и `model`. Пустой список допустимых продуктов даёт `recommendations=[]` и `model=null` без обращения к OpenRouter.

## Как устроен отбор

1. `eligibility_reasons()` проверяет сумму, срок, возраст бизнеса, залог, маркетплейс, действующий кредит и цель. Продукт с причиной исключения не передаётся LLM.
2. Для каждого допустимого продукта `ScoringEngine` вычисляет риск. Локальный `combined_score` использует веса 0.6 для `1 - risk_probability` и 0.4 для контекстной релевантности. Это эвристика ранжирования прототипа; она не калибрована как вероятность выдачи.
3. OpenRouter получает профиль, продуктовые правила и оценки кандидатов. Он выбирает порядок и пишет краткое основание. Сервер проверяет JSON, допустимый `product_id`, непустую причину и отсутствие повторов.

```python
from credit_advisor import CreditAdvisor, CreditAdvisorInput

profile = CreditAdvisorInput(
    requested_amount=800000,
    term_months=12,
    purpose="working_capital",
    business_age_months=16,
    monthly_revenue=1500000,
    net_margin_percent=18,
    debt_to_revenue_ratio=0.6,
    has_overdue_debt=False,
    credit_history_score=720,
    has_collateral=False,
    legal_form="ip",
    has_marketplace_sales=False,
    has_existing_business_loans=False,
    context_tags=("working_capital", "inventory"),
)
local_candidates = CreditAdvisor.default().recommend(profile, top_n=3)
```

Этот Python-пример показывает локальный фильтр. HTTP-маршрут дополнительно вызывает OpenRouter для итогового порядка.

## Ограничения и проверка

Публичные условия меняются; CSV — демонстрационный снимок, а не оферта. По умолчанию используется бесплатная модель OpenRouter `nvidia/nemotron-3.5-super-vl:free`. Чужой или повторный ID в ответе LLM даёт `502`, отсутствие ключа при наличии кандидатов — `503`, неверные входные значения — `422`. Проверка: `uv run pytest -q tests/test_credit_advisor.py tests/test_catalog_ids.py tests/test_api.py`.

[HTTP-контракт](../../docs/architecture/HTTP-API.md) · [Скоринг](../scoring/README.md)
