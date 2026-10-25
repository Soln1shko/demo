# API: список эндпоинтов

Базовый префикс: `/api/v1`. Формат: JSON (`application/json`), кроме загрузки файлов (`multipart/form-data`) и SSE (`text/event-stream`).
Документация генерируется автоматически: `/api/v1/docs` (Swagger UI), `/api/v1/redoc`, `/api/v1/openapi.json`.

Условные обозначения для ролей:

- 🌐 публичный
- 👤 `client`
- 🏦 `bank_analyst` / `bank_admin`
- 🔐 любой авторизованный

## Общие соглашения

| Тема | Правило |
|---|---|
| Авторизация | `Authorization: Bearer <access JWT>`. Refresh хранится в `httpOnly` cookie. |
| Контекст организации | Клиентские запросы к данным компании идут с `X-Organization-Id`. Либо `organization_id` в пути. Сервер проверяет членство. |
| Идемпотентность | Для `POST` с побочным эффектом (submit, sign, fund, withdraw, decide) обязателен `Idempotency-Key`. |
| Конкуренция | Мутации заявки принимают `version`. Несовпадение даёт `409 stale_version`. |
| Пагинация | `?limit=20&offset=0`. Ответ: `{items, total, limit, offset}`. |
| Ошибки | RFC 7807: `{type, title, status, detail, code, errors[]}` (для 422 это `errors: [{field, message}]`). |
| Деньги | В рублях, `number` с двумя знаками. Даты в ISO 8601 UTC. |
| ID заявки | Строка `AK-XXXXXXXX`. |
| Коды | 200, 201, 204, 400, 401, 403, 404, 409, 413, 415, 422, 429, 5xx. |

---

## 1. Аутентификация и аккаунт

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| POST | `/auth/register` | 🌐 | Регистрация клиента: `{name, email, password, demo_consent}`. Пароль не короче 8 символов. Возвращает access и устанавливает refresh cookie. `409`, если email занят. |
| POST | `/auth/login` | 🌐 | Вход клиента: `{email, password}`. Ошибка `401` с общим текстом «Почта или пароль не совпадают». |
| POST | `/auth/operator/login` | 🌐 | Вход сотрудника банка: `{operator_id, password}` (например `OP-2026`). Возвращает токен роли `bank_*`. |
| POST | `/auth/refresh` | 🌐 | Ротация refresh cookie и выдача нового access. |
| POST | `/auth/logout` | 🔐 | Инвалидация refresh. `204`. |
| GET | `/auth/me` | 🔐 | Профиль: id, name, email, роль, список организаций, `onboarding_complete`. |
| PATCH | `/auth/me` | 🔐 | Смена имени. |
| POST | `/auth/me/password` | 🔐 | Смена пароля: `{old_password, new_password}`. |
| POST | `/auth/me/reset-demo` | 👤 | Сброс кабинета: удаляет организации, заявки, черновики и документы аккаунта. Аккаунт остаётся. Требует `{confirm: true}`. |

---

## 2. Онбординг клиента

Состояние анкеты сохраняется на сервере. После перезахода клиент продолжает с того же шага.

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| GET | `/onboarding` | 👤 | Текущий черновик анкеты: `{step, legal, name, inn, region, age, profile, goal, amount, months, frequency, urgency, collateral, revenue, expenses, debt, seasonality, late}`. |
| PUT | `/onboarding` | 👤 | Сохранение шага (частичное обновление), ответ `200`. Серверная валидация шага. |
| POST | `/onboarding/complete` | 👤 | Завершение: создаёт организацию (с `finance_history` из анкеты, источник «Анкета») и возвращает её вместе с первичным подбором продуктов. |

---

## 3. Организации

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| GET | `/organizations` | 👤 | Список организаций пользователя. |
| POST | `/organizations` | 👤 | Новая организация: `{name, inn, legal, profile, revenue, expenses, debt, age}`. `409` при дубликате ИНН у пользователя. ИНН: 10 цифр для юрлица, 12 для ИП. |
| GET | `/organizations/{id}` | 👤 | Карточка. |
| PATCH | `/organizations/{id}` | 👤 | Изменение профиля: отрасль, цель, сумма и срок для подбора, обеспечение и т. д. |
| PATCH | `/organizations/{id}/financials` | 👤 | Редактирование показателей `{revenue, expenses, debt}` (неотрицательные значения). Не меняет уже отправленные заявки. |
| PUT | `/organizations/{id}/cash-balance` | 👤 | Доступный остаток денег `{amount}`. Фиксирует дату. |
| GET | `/organizations/{id}/finance-history` | 👤 | Помесячные показатели. Параметры: `months=3\|6\|12`. |
| PUT | `/organizations/{id}/finance-history/{month}` | 👤 | Добавить или заменить месяц (`YYYY-MM`, не в будущем): `{revenue, expenses, debt}`. Источник — «Месячный отчет». |
| DELETE | `/organizations/{id}/finance-history/{month}` | 👤 | Удалить месяц. |
| GET | `/organizations/{id}/analytics` | 👤 | Готовые расчёты для обзора: метрики (выручка, результат до кредитов, рентабельность, остаток), водопад, кредитная нагрузка и покрытие, сценарии выручки −30…+10%, ликвидность (runway), распределение заявок по группам статусов. Параметры: `months`, `series`. |
| POST | `/organizations/{id}/stress-test` | 👤 | Стресс-тест: `{amount, months, product_id?, revenue_shock_pct}`. Возвращает платёж, свободный поток, остаток после платежей, нагрузку, переплату и подсказку. |
| GET | `/organizations/{id}/draft` | 👤 | Текущий черновик заявки организации (или `null`). |
| PUT | `/organizations/{id}/draft` | 👤 | Создать или обновить черновик: `{product_id, step, amount, months, rate, scheme, days, fee, goal, company, inn, revenue, expenses, debt, age, late, consent, document_ids[]}`. Автосохранение. |
| DELETE | `/organizations/{id}/draft` | 👤 | Удалить черновик. |

---

## 4. Каталог продуктов и расчёты

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| GET | `/products` | 🔐 | Каталог. Фильтры: `category=working\|gap\|investment`, `secured=false`. Сортировка: `sort=match\|max\|name` (для `match` нужен `organization_id`). Возвращает условия, ставки, `features`, `discount`, `source_url`. |
| GET | `/products?include_all=true` | 🔐 | Все 11 кредитных продуктов справочника, включая 5 без калькулятора (`calculable=false`: нет ставок, расчёт и заявка недоступны, `422 product_not_calculable`). |
| GET | `/products/services` | 🔐 | Некредитные продукты банка (21 строка справочника). Фильтр `segment=msb\|corporate`. |
| GET | `/products/{id}` | 🔐 | Продукт. `id` — это `product_id` из CSV (`data/*.csv`), общий с ML: `business_loan`, `credit_line`, `overdraft`, `alfa_start`, `business_pledge_loan`, `business_mortgage` и др. |
| GET | `/products/special` | 🔐 | Специальные программы (селлеры, господдержка, РГО). |
| POST | `/products/match` | 👤 | Подбор: `{organization_id, goal, amount, months, collateral, frequency}`. Для каждого продукта возвращает `score`, `reasons[]`, `warnings[]`. Подбор не является одобрением. |
| POST | `/products/{id}/quote` | 🔐 | Расчёт: `{amount, months, days?, rate?, scheme?, fee?, stress_pct?, organization_id?}`. Возвращает `{interest, cost, total, first, last, peak, monthly, rest_at_peak, warnings, errors}`. |
| POST | `/products/{id}/schedule` | 🔐 | График платежей по тем же входным данным: `rows[{n, payment, principal, interest, balance}]`. |
| POST | `/products/compare` | 🔐 | Сравнение 2–3 продуктов: `[{product_id, quote_input}]`. Возвращает табличное представление. |

---

## 5. Заявки (клиент)

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| POST | `/applications` | 👤 | Отправка заявки из черновика: `{organization_id, consent: true, document_ids[]}`. Нужен `Idempotency-Key`. Валидация: цель, ИНН, показатели, ≥1 документ, согласие. Статус `submitted`, черновик удаляется, создаётся событие. `422` при ошибках. |
| GET | `/applications` | 👤 | Заявки текущей организации. Фильтр `filter=all\|active\|done` или `status=`. |
| GET | `/applications/{id}` | 👤 | Карточка: параметры, статус, `comment` банка, предложение (`offer_amount`), `risk` (после проверки), документы, `next_actions[]` (допустимые действия для статуса). |
| GET | `/applications/{id}/events` | 👤 | История заявки (таймлайн). |
| GET | `/applications/{id}/decision` | 👤 | «Почему такое решение»: скоринг, нагрузка, свободный поток, список сработавших правил, версия правил. Доступно после проверки. |
| GET | `/applications/{id}/schedule` | 👤 | График платежей по условиям заявки. |
| GET | `/applications/{id}/contract` | 👤 | Условия для подписания (для `approved`): сумма, ставка, платёж, итог, услуги. |
| GET | `/applications/{id}/export` | 👤 | Выгрузка данных заявки в JSON (файл). |
| POST | `/applications/{id}/supplement` | 👤 | Дополнение по запросу банка: `{answers{item_id:text}, document_ids[], comment?, version}`. Переход `needs_info → submitted`. Если запрос структурный, закрыть нужно каждый пункт (файл на каждый `document`, текст на `data`/`clarify`), иначе `422` со списком `errors[{field=item_id}]`. |
| POST | `/applications/{id}/accept-offer` | 👤 | Принять альтернативные условия (`alternative → approved`). Сохраняет `original_amount`. |
| POST | `/applications/{id}/sign` | 👤 | Подписание (демо): `{agreed: true, version}` (`approved → signed`). Идемпотентно. |
| POST | `/applications/{id}/fund` | 👤 | Подтвердить получение средств (`signed → funded`), симулятор выдачи. |
| POST | `/applications/{id}/withdraw` | 👤 | Отозвать заявку. Допустимо из `submitted`, `needs_info`, `review`, `approved`, `alternative`. `409` для остальных. |

> Единая точка для переходов с общей схемой тоже допустима: `POST /applications/{id}/transitions {action, version, reason?}`. Она остаётся в OpenAPI для совместимости с прежним контрактом. Явные action-эндпоинты выше являются основными.

Допустимые действия по статусам:

| Статус | Клиент | Банк |
|---|---|---|
| `submitted` | withdraw | check, assign, request_info |
| `checking` | не доступно (идёт проверка) | не доступно |
| `review` | withdraw | assign, request_info, decide |
| `needs_info` | supplement, withdraw | не доступно |
| `approved` | sign, withdraw | не доступно |
| `alternative` | accept-offer, withdraw | не доступно |
| `signed` | fund | не доступно |
| `funded`, `rejected`, `withdrawn` | новая заявка | не доступно |

---

## 6. Документы

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| POST | `/documents` | 👤 | Загрузка файла (`multipart`): `file`, `organization_id`, опционально `application_id` и `request_item` (id пункта запроса банка; новый файл заменяет прежний на этот пункт). PDF/JPG/PNG до 10 МБ. Проверка расширения, MIME и сигнатуры. Возвращает `{id, name, size, mime, kind}`. `413` и `415` при ошибке. |
| POST | `/documents/sample` | 👤 | Добавить синтетический образец выписки (демо); принимает `request_item`. Возвращает документ с `kind=sample`. |
| GET | `/documents` | 🔐 | Документы организации (для клиента) или заявки (для банка). Фильтры `organization_id`, `application_id`. |
| GET | `/documents/{id}` | 🔐 | Метаданные. |
| GET | `/documents/{id}/download` | 🔐 | Скачать файл или образец (стрим или `302` на presigned URL). Права проверяются. |
| DELETE | `/documents/{id}` | 👤 | Удалить, если он ещё не привязан к отправленной заявке. |
| GET | `/applications/{id}/documents` | 🔐 | Комплект документов заявки. |

---

## 7. Банк: рабочее место

Все эндпоинты под `/bank/*` требуют роли `bank_analyst` или `bank_admin`.

### 7.1 Очередь и карточка

| Метод | Путь | Описание |
|---|---|---|
| GET | `/bank/applications` | Очередь. Фильтры: `lane=inbox\|new\|system\|waiting\|done` (рабочая корзина: к работе, ещё не проверялись, система уже проверила, ждём клиента, отработанные), `status`, `owner=all\|mine\|free`, `product_id`, `period=all\|1\|7\|30` (дни), `q` (компания, ИНН или номер), `sort=oldest\|newest\|amount\|priority`, пагинация. В строке есть `hours_in_queue`, `score` и `operator_decided` (аналитик уже зафиксировал решение; автоматическое решение системы — `false`). |
| GET | `/bank/applications/stats` | Счётчики статусов и рабочих корзин: `inbox`, `fresh`, `system`, `waiting`, `done`. |
| GET | `/bank/applications/{id}` | Досье: параметры заявки, данные компании, документы, результаты внешних проверок, скоринг, чек-лист, заметка, история, расчёт платежей (максимум, проценты и услуги, остаток в месяц пика). Включает сводку для аналитика (`summary`, с пометкой об автогенерации). |
| GET | `/bank/applications/{id}/events` | Полная история событий (аудит). |
| POST | `/bank/applications/{id}/assign` | Взять в работу: `{assignee_id?}` (по умолчанию текущий оператор). `submitted → review`. |
| POST | `/bank/applications/assign-bulk` | Массовое назначение: `{application_ids[]}`. |

### 7.2 Проверки и решение

| Метод | Путь | Описание |
|---|---|---|
| POST | `/bank/applications/{id}/check` | Запустить автопроверку (`submitted/review → checking`). Ставит задачу в очередь воркера. Возвращает `202` и `check_id`. |
| GET | `/bank/applications/{id}/check` | Ход проверки: шаги «комплект», «ФНС», «БКИ», «скоринг», «решение» со статусом и временем. |
| GET | `/bank/applications/{id}/external-checks` | Результаты симуляторов: `fns` (статус, ОКВЭД, руководители, адрес), `bki` (обязательства, просрочки). |
| GET | `/bank/applications/{id}/scoring` | Скоринг: балл, нагрузка, факторы и их вклад, версия правил. |
| POST | `/bank/applications/{id}/request-info` | Запросить сведения одним запросом: `{items[{kind: document|data|clarify, title, template_id?}], message?, version}`, до 12 пунктов. Переход `→ needs_info`. `422`, если пунктов нет. Старый формат `{text, version}` поддерживается. Шаблоны: `GET /bank/request-templates` (с полем `kind`). |
| POST | `/bank/applications/{id}/decision` | Ручное решение: `{decision: approved\|rejected\|alternative, reason (≥10 символов), offer_amount?, version}`. Для `alternative` сумма должна быть не ниже минимума продукта. Принимается из `review`, а также пересматривает автоматическое решение из `approved`, `alternative` и `rejected`, пока клиент не подписал условия (после подписания `409`). В истории такое решение помечено как «пересмотрено аналитиком». |
| PUT | `/bank/applications/{id}/checklist` | Чек-лист рассмотрения: `{key: numbers\|debt\|collateral, checked}`. Пишет событие. |
| PUT | `/bank/applications/{id}/note` | Внутренняя заметка аналитика `{text}`. Клиенту не видна. |
| GET | `/bank/request-templates` | Шаблоны пунктов запроса, сгруппированные по `kind`: `document` (справка о доходах, кредитные договоры, выписка…), `data` (платежи, выручка…), `clarify` (источник, залог, цель). |
| GET | `/bank/decisions` | История решений: заявки в статусах `approved`, `alternative`, `rejected`, `signed`, `funded`, `withdrawn`. Пагинация. |

### 7.3 Поддержка

| Метод | Путь | Описание |
|---|---|---|
| GET | `/bank/support/tickets` | Обращения клиентов. Фильтр `status=open\|answered`. |
| GET | `/bank/support/tickets/{id}` | Обращение с перепиской и контекстом (компания, заявка). |
| POST | `/bank/support/tickets/{id}/reply` | Ответ клиенту `{text}` (минимум 3 символа). |
| PATCH | `/bank/support/tickets/{id}` | Закрыть или переоткрыть. |

### 7.4 Администрирование и демо

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| GET | `/bank/me` | 🏦 | Профиль оператора (ID, имя, роль). |
| GET | `/bank/scoring/rules` | 🏦 | Текущие правила скоринга и решения в читаемом виде («Прозрачная демомодель»). |
| PUT | `/bank/scoring/rules` | `bank_admin` | Изменить параметры правил (пороги, штрафы). Увеличивает `rules_version`. |
| POST | `/bank/demo/scenarios` | 🏦 | Создать синтетическую заявку: `{kind: good\|alt\|manual\|bad}`. Для демонстрации четырёх исходов. |
| GET | `/bank/audit` | `bank_admin` | Аудит: фильтры `application_id`, `actor`, `type`, период. Проверка целостности хеш-цепочки: `GET /bank/audit/verify`. |

---

## 8. Новостная лента (персонализация)

Требование кейса: на демо показать, как лента меняется под клиента и что в новостях.

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| GET | `/feed` | 👤 | Лента организации. Учитывает отрасль, цель, статус заявок, показатели и сезон. Параметры: `organization_id`, `profile=retail\|production\|services` (для предпросмотра другой отрасли), `limit`. Каждый элемент: `{id, kind, title, body, icon, cta{label, route}, reason}`. |
| GET | `/feed/explain` | 👤 | «Почему вы это видите»: профиль, число заявок, активные правила персонализации. |
| POST | `/feed/{id}/dismiss` | 👤 | Скрыть элемент. |
| GET | `/feed/next-step` | 👤 | Персональная рекомендация «следующий шаг» для обзора (запрос документов, одобрено, стресс-тест, подбор продукта). |
| GET | `/feed/items` | `bank_admin` | Редакционный каталог новостей. |
| POST | `/feed/items` | `bank_admin` | Добавить или изменить новость и условия показа (`conditions`). |

---

## 9. Помощник и поддержка

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| POST | `/assistant/conversations` | 👤 | Создать диалог. Вернёт приветствие и быстрые вопросы. |
| GET | `/assistant/conversations/{id}` | 👤 | История сообщений. |
| POST | `/assistant/conversations/{id}/messages` | 👤 | Вопрос: `{text, organization_id?}`. Ответ обычным JSON либо потоком SSE (`Accept: text/event-stream`). Ответ строится на данных заявок и правилах. Может содержать карточку продукта (`product_card`). При недоступной LLM используется сценарный fallback. |
| POST | `/assistant/conversations/{id}/escalate` | 👤 | Позвать оператора: создаёт обращение (`ticket`). Если открытое уже есть, возвращает его. |
| GET | `/support/tickets` | 👤 | Обращения клиента. |
| GET | `/support/tickets/{id}` | 👤 | Обращение с ответами оператора. |
| POST | `/support/tickets/{id}/messages` | 👤 | Дополнить обращение. |

---

## 10. Уведомления и реальное время

В сценарии нет email и SMS: всё работает внутри продукта.

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| GET | `/events/stream` | 🔐 | SSE-поток. Клиент получает: `application.updated`, `application.check_progress`, `ticket.replied`. Банк получает: `queue.updated`, `application.created`, `application.supplemented`. Поддерживается `Last-Event-ID`. |
| GET | `/notifications` | 🔐 | Список уведомлений. Параметры `unread=true`. |
| POST | `/notifications/{id}/read` | 🔐 | Пометить прочитанным. |
| POST | `/notifications/read-all` | 🔐 | Пометить все. |

---

## 11. Симуляторы внешних систем

Работают как отдельные адаптеры. По HTTP они доступны только внутри окружения (для отладки): префикс `/internal/mock/*`, защищён сервисным токеном. Данные детерминированно генерируются по ИНН. Это допустимо по требованиям кейса: «локальные моки, стабы или симуляторы».

| Метод | Путь | Описание |
|---|---|---|
| GET | `/internal/mock/fns/company/{inn}` | ЕГРЮЛ/ЕГРИП и «Прозрачный бизнес»: статус (`active`, `liquidating`), дата регистрации, ОКВЭД, руководитель, учредители, адрес, признаки риска. |
| GET | `/internal/mock/bki/report/{inn}` | Кредитная история: обязательства, суммы, просрочки, платёжная дисциплина. |
| POST | `/internal/mock/esign/sign` | Симулятор подписи: возвращает идентификатор «подписи» с временной меткой. |
| POST | `/internal/mock/payout/disburse` | Симулятор выдачи: подтверждение «перевода». Реальных операций нет. |

Публичные обёртки для клиента:

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| GET | `/lookup/company?inn=` | 👤 | Подсказка по ИНН при онбординге (название, ОКВЭД, статус) из симулятора ФНС. Помогает «сократить повторный ввод». |

---

## 12. Служебные

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health/live` | Процесс жив. Без авторизации. |
| GET | `/health/ready` | Готовность: Postgres, Redis, MinIO. |
| GET | `/version` | Версия приложения, commit hash, `rules_version`. |
| GET | `/metrics` | Prometheus. Только внутренняя сеть. |
| GET | `/api/v1/openapi.json`, `/api/v1/docs`, `/api/v1/redoc` | Контракт и Swagger UI. |

---

## 13. События SSE (`/events/stream`)

| Событие | Кому | Данные |
|---|---|---|
| `application.updated` | клиент организации | `{id, status, version}` |
| `application.check_progress` | клиент и аналитик | `{id, step, total, label}`: шаги «Проверяем комплект», «Сверяем данные», «Оцениваем нагрузку», «Формируем решение». |
| `application.created` | банк | `{id, company, amount}` |
| `application.supplemented` | банк | `{id}` |
| `queue.updated` | банк | `{counts}` |
| `ticket.replied` | клиент | `{ticket_id}` |

---

## 14. Сводка по экранам фронтенда

| Экран | Основные эндпоинты |
|---|---|
| Вход и регистрация | `/auth/register`, `/auth/login`, `/auth/me` |
| Вход банка | `/auth/operator/login`, `/bank/me` |
| Онбординг | `/onboarding`, `/lookup/company`, `/onboarding/complete`, `/products/match` |
| Обзор (аналитика) | `/organizations/{id}/analytics`, `/organizations/{id}/finance-history`, `/feed/next-step`, `/applications` |
| Каталог продуктов | `/products`, `/products/match`, `/products/{id}/quote`, `/products/{id}/schedule`, `/products/compare` |
| Заявка (4 шага) | `/organizations/{id}/draft`, `/documents`, `/documents/sample`, `/applications` |
| Мои заявки и карточка | `/applications`, `/applications/{id}`, `/…/events`, `/…/decision`, `/…/supplement`, `/…/accept-offer`, `/…/sign`, `/…/fund`, `/…/withdraw`, `/…/schedule`, `/…/export` |
| Документы | `/documents`, `/documents/{id}/download` |
| Лента | `/feed`, `/feed/explain`, `/feed/{id}/dismiss` |
| Помощник | `/assistant/*`, `/support/tickets` |
| Модели ML | `/ml/banners`, `/ml/advisor`, `/ml/score`, `/ml/cash-gap`, `/ml/twin`, `/ml/quest`, `/ml/quest/recalculate`, `/ml/parse`, `/ml/copilot`, `/ml/applications/{id}/brief`, `/ml/applications/{id}/recovery`, `/ml/applications/{id}/explain`, `/ml/applications/{id}/score` |
| Настройки и организации | `/organizations`, `/organizations/{id}/financials`, `/auth/me/reset-demo` |
| Очередь банка | `/bank/applications`, `/bank/applications/stats`, `/bank/applications/assign-bulk` |
| Карточка банка | `/bank/applications/{id}`, `/check`, `/external-checks`, `/request-info`, `/decision`, `/checklist`, `/note` |
| Обращения и история | `/bank/support/tickets`, `/bank/decisions` |

---

## 15. Тестовые учётные записи (сидинг)

| Роль | Логин | Пароль |
|---|---|---|
| Клиент (пустой) | `new@demo.ru` | `Demo2026!` |
| Клиент (с данными) | `client@demo.ru` | `Demo2026!` |
| Аналитик банка | `OP-2026` | `Alfa2026!` |
| Администратор банка | `ADM-2026` | `Alfa2026!` |

Это тестовые данные для демонстрации. Реальные пароли использовать нельзя. Значения задаются через `.env` и CLI-сидер (`python -m app.cli seed`).

