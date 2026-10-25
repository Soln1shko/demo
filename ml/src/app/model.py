"""Общий строгий контракт для входных и выходных моделей API."""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Pydantic-модель, отклоняющая неизвестные поля.

    Attributes:
        model_config: Правило запрета дополнительных полей.
    """

    model_config = ConfigDict(extra="forbid")
