FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir "uv>=0.7,<1" && uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
COPY data ./data
RUN uv sync --frozen --no-dev

# Энкодер для RAG входит в образ. Volume /app/model пуст на новом сервере и
# перекрыл бы файлы образа, поэтому startup-скрипт копирует туда кеш один раз.
RUN EMBEDDING_CACHE_PATH=/opt/model-cache uv run --no-sync python -c \
    "from ai_assistant.encoder import MultilingualEncoder; assert len(MultilingualEncoder().encode('проверка')) > 0"
COPY docker-entrypoint.sh /usr/local/bin/ml-entrypoint
RUN chmod +x /usr/local/bin/ml-entrypoint

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/ml-entrypoint"]
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
