# Сторонние компоненты

Все демонстрационные данные в проекте синтетические. Текстовые ML-функции при наличии ключа отправляют обезличенные данные в OpenRouter; бесплатный endpoint ограничен по числу запросов и зависит от доступности провайдера. Локальные формулы, скоринг и сценарии работают без него.

## Шрифты (встроены в `frontend/public/fonts`)
- **Raleway** — SIL Open Font License 1.1 (The Raleway Project Authors).
- **Unbounded** — SIL Open Font License 1.1 (The Unbounded Project Authors).

## Иконки
- **lucide-react** — ISC License.

## Frontend (npm, точные версии — `frontend/package-lock.json`)
React, React DOM, React Router (MIT); TanStack Query (MIT); Zustand (MIT); Vite, Vitest (MIT);
Tailwind CSS, PostCSS, Autoprefixer (MIT); TypeScript (Apache-2.0).

## Backend (Python, точные версии — `backend/uv.lock`)
FastAPI, Starlette, Uvicorn, sse-starlette (MIT/BSD); Pydantic, pydantic-settings (MIT);
SQLAlchemy, Alembic (MIT); asyncpg (Apache-2.0); aiosqlite (MIT); redis-py (MIT); ARQ (MIT);
PyJWT (MIT); argon2-cffi (MIT); structlog (MIT/Apache-2.0); prometheus-fastapi-instrumentator (ISC);
httpx (BSD-3); pytest, pytest-asyncio, hypothesis (MPL-2.0), ruff (MIT), mypy (MIT).

## ML (Python, точные версии — `ml/uv.lock`)
PaddleOCR/PaddlePaddle распознают текст документов, FastEmbed и Qdrant обеспечивают поиск по справочной базе. В коде указаны `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` для поиска, `PP-OCRv5_mobile_det`, `cyrillic_PP-OCRv5_mobile_rec` и `PP-DocLayout-M` для OCR. Отдельные лицензии весов и источники загрузки следует сверять перед распространением образа. Текстовые функции используют бесплатный endpoint OpenRouter `nvidia/nemotron-3.5-super-vl:free` только при заданном ключе; распознанный текст синтетических документов передаётся этому внешнему сервису. NVIDIA предупреждает, что запросы к бесплатному endpoint могут записываться для улучшения сервиса; в проекте разрешены только синтетические данные.

## Инфраструктура (Docker-образы)
PostgreSQL (PostgreSQL License), Redis 7 (BSD-3), nginx (BSD-2), MinIO (AGPL-3.0, опциональный профиль),
Ollama (MIT, опциональный профиль). Модель по умолчанию — `qwen2.5:7b-instruct` (Apache-2.0, открытые веса),
загружается пользователем отдельно и по умолчанию отключена.

## Смоделированные интеграции

В основном сценарии нет соединения с реальными ФНС, БКИ, системой электронной подписи и платёжным контуром банка. Их ответы создают локальные детерминированные симуляторы по демонстрационным данным. Подписание и выдача меняют только состояние заявки в прототипе; деньги не перечисляются. DaData используется только при отдельно заданном `DADATA_API_KEY` для подсказки компании по ИНН и не требуется для демо.

Исходные каталоги продуктов в `data/*.csv` служат справочным снимком для демонстрации, не являются банковской офертой и требуют сверки с официальными условиями перед иным использованием. Детали ML-компонентов и загружаемых весов — в [ml/THIRD_PARTY_NOTICES.md](ml/THIRD_PARTY_NOTICES.md).
