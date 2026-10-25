import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_demo_defaults() -> None:
    with pytest.raises(ValidationError, match="SEED_ON_START"):
        Settings(app_env="prod", seed_on_start=True, _env_file=None)


def test_demo_mode_allows_local_stack() -> None:
    settings = Settings(app_env="demo", seed_on_start=True, _env_file=None)
    assert settings.seed_on_start


def test_production_accepts_hardened_configuration() -> None:
    settings = Settings(
        app_env="prod",
        seed_on_start=False,
        create_tables_on_start=False,
        cookie_secure=True,
        jwt_secret="a" * 48,
        internal_token="b" * 32,
        database_url="postgresql+asyncpg://user:password@db/app",
        _env_file=None,
    )
    assert settings.app_env == "prod"
