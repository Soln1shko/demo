"""Конфигурация приложения из переменных окружения (12-factor)."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "demo", "prod"] = "dev"
    commit_sha: str = "dev"
    api_prefix: str = "/api/v1"

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    redis_url: str | None = None

    jwt_secret: str = "dev-secret-change-me-please-use-32+bytes"
    access_ttl_min: int = 15
    refresh_ttl_days: int = 14
    cookie_secure: bool = False
    password_hash_fast: bool = False  # только для тестов
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    storage_backend: Literal["local", "s3"] = "local"
    storage_dir: str = "./data/files"
    s3_endpoint: str | None = None
    s3_bucket: str = "alfa-documents"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    max_upload_bytes: int = 10 * 1024 * 1024

    llm_base_url: str | None = None  # например http://ollama:11434
    llm_model: str = "qwen2.5:7b-instruct"
    ml_base_url: str | None = None  # http://ml:8000 в compose, пусто — кабинет работает без модели

    dadata_api_key: str | None = None  # поиск компании по ИНН; без ключа — демо-симулятор ФНС

    check_step_delay: float = 0.6  # пауза между шагами автопроверки (для анимации)
    auto_check_on_submit: bool = False
    seed_on_start: bool = True
    create_tables_on_start: bool = True  # для dev/test; в проде применяются миграции Alembic
    internal_token: str = "dev-internal-token"
    rate_limit_enabled: bool = True

    demo_client_password: str = "Demo2026!"
    demo_operator_password: str = "Alfa2026!"

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.app_env != "prod":
            return self
        if self.seed_on_start or self.create_tables_on_start:
            raise ValueError("В prod отключите SEED_ON_START и CREATE_TABLES_ON_START")
        if not self.cookie_secure:
            raise ValueError("В prod требуется COOKIE_SECURE=true")
        if (
            self.jwt_secret
            in {"dev-secret-change-me-please-use-32+bytes", "change-me-in-real-deployments-0123456789abcdef"}
            or len(self.jwt_secret) < 32
        ):
            raise ValueError("В prod задайте собственный JWT_SECRET длиной от 32 символов")
        if self.internal_token == "dev-internal-token" or len(self.internal_token) < 24:
            raise ValueError("В prod задайте собственный INTERNAL_TOKEN длиной от 24 символов")
        if self.database_url.startswith("sqlite"):
            raise ValueError("В prod требуется PostgreSQL")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
