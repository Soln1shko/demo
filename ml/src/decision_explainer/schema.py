"""Запрос кнопки CRM и готовое сообщение для предпринимателя."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.model import StrictModel
from underwriting.schema import SuppliedScoring, UnderwritingResponse


class RefusalExplanationRequest(StrictModel):
    """Сотрудник выбрал отказ; резюме уже сформировано андеррайтингом.

    Attributes:
        decision: Уже выбранное сотрудником решение об отказе.
        underwriting: Готовое резюме заявки с рисками.
        scoring: Необязательные факторы готового скоринга.
    """

    decision: Literal["declined"]
    underwriting: UnderwritingResponse
    scoring: SuppliedScoring | None = None

    @model_validator(mode="after")
    def consistent_scoring_version(self) -> RefusalExplanationRequest:
        """Проверяет согласованность версий скоринга.

        Returns:
            RefusalExplanationRequest: Проверенный запрос объяснения отказа.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        if self.scoring and self.scoring.model_version != self.underwriting.scoring_model_version:
            raise ValueError("Версия скоринга не совпадает с использованной в резюме заявки.")
        return self


class RefusalExplanationResponse(StrictModel):
    """Сообщение клиенту с причиной отказа.

    Attributes:
        message: Готовое сообщение клиенту.
    """

    message: str = Field(min_length=1, max_length=500)


class GeneratedExplanation(StrictModel):
    """Ответ LLM с опорными рисками.

    Attributes:
        message: Готовое сообщение клиенту.
        risk_indexes: Индексы использованных рисков резюме.
    """

    message: str = Field(min_length=1, max_length=500)
    risk_indexes: list[int] = Field(min_length=1, max_length=2)
