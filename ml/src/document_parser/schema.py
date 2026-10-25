"""Фиксированный профиль, дополнительные факты и ссылки на исходные страницы."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.model import StrictModel


class CustomerProfile(StrictModel):
    """Универсальный профиль клиента.

    Attributes:
        legal_form: Организационно-правовая форма.
        tax_regime: Налоговый режим.
        tax_id: Демонстрационный налоговый идентификатор.
        registration_number: Демонстрационный номер регистрации.
        industry: Отрасль бизнеса.
        business_age_months: Возраст бизнеса в месяцах.
        monthly_revenue: Месячная выручка.
        monthly_expenses: Месячные расходы.
        net_margin_percent: Чистая маржа в процентах.
        existing_debt_balance: Остаток действующего долга.
        monthly_debt_payment: Ежемесячный платёж по долгу.
    """

    legal_form: Literal["ip", "ooo"] | None = None
    tax_regime: str | None = None
    tax_id: str | None = None
    registration_number: str | None = None
    industry: str | None = None
    business_age_months: int | None = Field(default=None, ge=0)
    monthly_revenue: int | None = Field(default=None, ge=0)
    monthly_expenses: int | None = Field(default=None, ge=0)
    net_margin_percent: float | None = Field(default=None, ge=0, le=100)
    existing_debt_balance: int | None = Field(default=None, ge=0)
    monthly_debt_payment: int | None = Field(default=None, ge=0)


class FieldEvidence(StrictModel):
    """Источник извлечённого поля профиля.

    Attributes:
        field: Название извлечённого поля.
        document_id: Идентификатор документа.
        page: Номер страницы.
        source_text: Текст из документа.
    """

    field: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    source_text: str = Field(min_length=1, max_length=300)


class AdditionalFact(StrictModel):
    """Дополнительный факт из документа.

    Attributes:
        name: Название факта.
        value: Значение факта или признака.
        document_id: Идентификатор документа.
        page: Номер страницы.
        source_text: Текст из документа.
    """

    name: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)
    document_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    source_text: str = Field(min_length=1, max_length=300)


class FieldConflict(StrictModel):
    """Противоречие между документами.

    Attributes:
        field: Название извлечённого поля.
        description: Описание документа или продукта.
        document_ids: Идентификаторы исходных документов.
    """

    field: str
    description: str
    document_ids: list[str]


class ParsedProfile(StrictModel):
    """Извлечённый профиль с источниками.

    Attributes:
        profile: Профиль клиента или бизнеса.
        additional_facts: Дополнительные факты из источника.
        field_evidence: Источники заполненных полей.
        conflicts: Противоречия документов.
    """

    profile: CustomerProfile
    additional_facts: list[AdditionalFact] = Field(max_length=20)
    field_evidence: list[FieldEvidence] = Field(max_length=40)
    conflicts: list[FieldConflict] = Field(max_length=20)

    @model_validator(mode="after")
    def sourced_fields(self) -> ParsedProfile:
        """Проверяет происхождение извлечённых полей.

        Returns:
            ParsedProfile: Профиль с подтверждёнными полями.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        supported = {item.field for item in self.field_evidence}
        for name, value in self.profile.model_dump().items():
            if value is not None and name not in supported:
                raise ValueError(f"Для поля {name} нет ссылки на документ.")
        if any(item.field not in CustomerProfile.model_fields for item in self.field_evidence):
            raise ValueError("В field_evidence указано неизвестное поле профиля.")
        return self


class DocumentParseResponse(ParsedProfile):
    """Ответ сервиса обработки документов.

    Attributes:
        case_id: Демонстрационный идентификатор заявки.
        missing_fields: Поля профиля без подтверждённых значений.
        model: Название использованной LLM.
        synthetic: Признак демонстрационных данных.
    """

    case_id: str
    missing_fields: list[str]
    model: str
    synthetic: bool = True
