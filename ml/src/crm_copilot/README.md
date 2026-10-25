# CRM Copilot для сотрудника

`POST /v1/crm-copilot/reply` собирает историю обращения и снимок заявки, показывает, чего не хватает для однозначного ответа клиенту, предлагает следующие действия и черновик сообщения. Сервис не читает CRM сам, не меняет заявку и не отправляет сообщение. Сотрудник подтверждает текст перед отправкой.

## Вход

Обязательны `case_id` вида `DEMO-*` и `customer_question`. Остальной контекст бэк добавляет по мере наличия:

| Поле | Что означает |
| --- | --- |
| `history[]` | Сообщения с уникальным `message_id`, `author: customer|employee|system`, текстом |
| `application` | Статус, кредитный продукт, сумма, срок, цель, решение и его причина, если уже есть |
| `profile` | Подтверждённый универсальный профиль клиента |
| `scoring` | Готовый риск и факторы; Copilot не пересчитывает скоринг |
| `checks[]` | Проверки `clear|flag|missing` с ID и источником |
| `documents[]` | Статус `missing|uploaded|reviewing|verified|rejected` для документа |
| `underwriting` | Резюме **того же** `case_id`; связность проверяет входная схема |
| `verified_facts[]` | Подтверждённые бэком сведения с `fact_id` и `source` |
| `required_fields[]` | Поля, обязательные для ответа на конкретный вопрос: `path`, `label`, `reason`, `obtain_from`, опциональные `acceptable_values[]` |

`obtain_from` принимает `customer`, `employee`, `backend`, `document` или `check`. Если клиент спрашивает о дате решения, бэк может потребовать `verified_facts.decision_deadline.text`; если о результате, `application.decision` со значениями `approved` или `declined`. Требования бэка проверяются **независимо от вывода LLM**. Если `required_fields` не задан, полнота вопросно-зависимых данных не гарантирована: модель может обнаружить пробелы, но не заменяет явный контракт бэка.

## Выход и логика

| Поле | Значение |
| --- | --- |
| `answerability` | `ready` либо `needs_data`: готовность черновика, не статус кредитной заявки |
| `summary`, `summary_evidence[]` | Краткая история обращения и пути к источникам |
| `missing_data[]` | `path`, название, причина отсутствия и у кого получить |
| `next_actions[]` | Следующие действия сотрудника, с источниками при наличии |
| `reply_draft`, `reply_evidence[]` | Текст клиенту и подтверждённые поля, на которых он основан |
| `requires_employee_confirmation` | Всегда `true`; сотрудник проверяет сообщение |
| `model`, `synthetic` | Модель OpenRouter и демонстрационный признак |

Сервер строит список реально присутствующих скалярных полей, отправляет его с вопросом в OpenRouter, проверяет ссылки модели и добавляет пропуски из `required_fields`. Если чего-то не хватает, сервер заменяет черновик LLM на запрос уточнений, а `reply_evidence` делает пустым. Если данных хватает, ссылка только на сообщение клиента или его вопрос не считается подтверждением факта. При полном отсутствии контекста заявки сервис сообщает о нехватке `case_context`.

## Синтетический пример

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/crm-copilot/reply \
  -H 'content-type: application/json' \
  -d '{"case_id":"DEMO-CRM-1","customer_question":"Когда будет решение?","history":[{"message_id":"m1","author":"customer","text":"Когда будет решение по кредиту?"}],"application":{"status":"document_review","decision":"pending"},"required_fields":[{"path":"verified_facts.decision_deadline.text","label":"Подтверждённый срок решения","reason":"Без него нельзя назвать дату.","obtain_from":"backend"}]}'
```

При корректном ответе LLM ключевой результат — `answerability: "needs_data"`, путь `verified_facts.decision_deadline.text` в `missing_data` и черновик без обещанной даты. Точная формулировка текста может меняться.

## Ошибки и проверка

Неверный снимок, повторяющийся ID или резюме другой заявки дают `422`. Чужая ссылка или неверный JSON LLM — `502`; недоступность OpenRouter — `503`. Проверка: `uv run pytest -q tests/test_crm_copilot.py tests/test_api.py`. Тесты используют подменный LLM-клиент и не подтверждают качество живого ответа.

[HTTP-контракт](../../docs/architecture/HTTP-API.md) · [Архитектура](../../../docs/architecture.md)
