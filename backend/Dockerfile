FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# uv ставится из PyPI (не из ghcr.io — тот может быть недоступен из некоторых сетей)
RUN pip install --no-cache-dir "uv>=0.5,<1"
WORKDIR /srv

# зависимости отдельным слоем — кэшируются, пока не менялись lock-файлы
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN useradd --system --uid 10001 app && mkdir -p /srv/data/files && chown -R app /srv/data
USER app
ENV PATH="/srv/.venv/bin:$PATH" CREATE_TABLES_ON_START=false APP_ENV=prod
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live')"

# миграции применяются при старте; сидинг идемпотентен (SEED_ON_START)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
