# ML-сервис Альфа Пульс

Отдельный FastAPI-сервис получает синтетический профиль и расчёты от backend. Его задача — оценить риск, найти допустимые предложения, посчитать денежные сценарии и подготовить подсказки для клиента и аналитика. **Итоговое решение по заявке остаётся за продуктовыми правилами и сотрудником банка.** Полный путь в браузере описан в [корневом README](../README.md).

## Запуск

Для проверки всего продукта запускайте Compose из корня репозитория. Если нужен только ML API:

```bash
cd ml
docker compose up -d --build --wait
```

После старта доступны [Swagger](http://localhost:8000/docs), [OpenAPI JSON](http://localhost:8000/openapi.json) и [health](http://localhost:8000/health). На первой сборке нужен интернет для загрузки энкодера поиска; OCR может загрузить модель при первом запросе. Для этих контейнеров используется `linux/amd64`, на ARM возможна эмуляция. Версии Python и зависимостей закреплены в `Dockerfile`, `pyproject.toml` и `uv.lock`.

## Компоненты

| Сервис | Результат | Внешний ключ |
| --- | --- | --- |
| [Scoring](src/scoring/README.md) | Риск и вклад факторов | Нет |
| [Credit Advisor](src/credit_advisor/README.md) | Отбор кредитов по правилам, затем текстовое ранжирование | Для текстового этапа OpenRouter |
| [NBA](src/nba/README.md) | Некредитные предложения | Нет |
| [Cash Gap](src/cash_cap/README.md) | Вероятность и причины кассового разрыва | Нет |
| [Business Twin и Credit Quest](src/financial_intelligence/README.md) | Сценарии остатков и варианты улучшения заявки | Нет |
| [Document Parser](src/document_parser/README.md) | Извлечение полей из документа с подтверждением | OCR локально; для текстовой нормализации OpenRouter |
| [Underwriting](src/underwriting/README.md) | Сводка и вопросы аналитику | Для текста OpenRouter |
| [Decision Explainer](src/decision_explainer/README.md) | Черновик причины отказа | OpenRouter |
| [Offer Recovery](src/offer_recovery/README.md) | Допустимые альтернативные условия | Нет |
| [CRM Copilot](src/crm_copilot/README.md) | Черновик ответа клиенту | OpenRouter |
| [AI Assistant](src/ai_assistant/README.md) | Поиск по базе знаний и ответ с источниками | Поиск локально; для ответа OpenRouter |

`OPENROUTER_API_KEY` необязателен для запуска: локальные расчёты, правила и поиск работают без него. Для HTTP-подбора Credit Advisor и остальных генеративных функций нужен ключ OpenRouter. По умолчанию используется бесплатная `nvidia/nemotron-3.5-super-vl:free`; её доступность и лимиты задаёт внешний провайдер. Для демо ключ уже указан в корневом `.env.example`; скопируйте этот файл в `.env`. В полной системе backend вызывает ML из внутренней сети Compose, а браузер обращается только к backend.

## Проверка

Контракты запросов и ответов — в [описании ML API](docs/architecture/HTTP-API.md) и Swagger. Пример локального расчёта:

```bash
curl -sS -X POST http://localhost:8000/v1/scoring \
  -H 'content-type: application/json' \
  -d '{"product_id":"business_loan","requested_amount":2000000,"term_months":36,"business_age_months":28,"monthly_revenue":1500000,"net_margin_percent":18,"debt_to_revenue_ratio":0.8,"has_overdue_debt":false,"credit_history_score":720,"has_collateral":false,"legal_form":"ip"}'
```

Ответ содержит `risk_probability`, `risk_band`, `factors` и `model_version`. Для проверок исходников нужны Python 3.13 и `uv`:

```bash
cd ml
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest -q
```

Каталоги в `data/*.csv` содержат справочные условия и демонстрационные правила. Модели и сценарии не обучены на реальных банковских заявках и не подходят для настоящего кредитования. Ограничения и допущения описаны в README каждого сервиса; внешние компоненты — в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
