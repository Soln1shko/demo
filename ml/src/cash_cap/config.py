"""Конфигурация локального cash-gap baseline."""

from pathlib import Path

HISTORY_DAYS = 60
FORECAST_DAYS = 30
MODEL_PATH = Path(__file__).with_name("model_weights.json")
