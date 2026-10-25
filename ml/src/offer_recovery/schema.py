"""Контракт отказов, рекомендованных кредитов и локально рассчитанных вариантов."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.schemas import ApiModel, CreditAdvisorRequest


class DeclinedOffer(ApiModel):
    """Ранее отклонённое кредитное предложение.

    Attributes:
        product_id: Идентификатор кредитного продукта.
        requested_amount: Запрошенная сумма кредита.
        term_months: Срок кредита в месяцах.
        reasons: Причины выбора или отказа.
    """

    product_id: str = Field(min_length=1)
    requested_amount: int = Field(gt=0)
    term_months: int = Field(gt=0)
    reasons: list[str] = Field(min_length=1, max_length=10)


class RecoveryRequest(ApiModel):
    """Запрос альтернативных условий кредита.

    Attributes:
        case_id: Демонстрационный идентификатор заявки.
        profile: Профиль клиента или бизнеса.
        declined_offers: Ранее отклонённые предложения.
        recommended_product_ids: Идентификаторы рекомендованных кредитов.
        minimum_acceptable_amount: Минимально приемлемая сумма.
        minimum_acceptable_term_months: Минимально приемлемый срок.
    """

    case_id: str = Field(pattern=r"^DEMO-[A-Z0-9-]{1,24}$")
    profile: CreditAdvisorRequest
    declined_offers: list[DeclinedOffer] = Field(min_length=1, max_length=10)
    recommended_product_ids: list[str] = Field(min_length=1, max_length=11)
    minimum_acceptable_amount: int = Field(gt=0)
    minimum_acceptable_term_months: int = Field(gt=0)

    @model_validator(mode="after")
    def unique_products(self) -> RecoveryRequest:
        """Обрабатывает `unique_products`.

        Returns:
            RecoveryRequest: Проверенный запрос альтернатив.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        if len(self.recommended_product_ids) != len(set(self.recommended_product_ids)):
            raise ValueError("recommended_product_ids должны быть уникальны.")
        if self.minimum_acceptable_amount > self.profile.requested_amount:
            raise ValueError("Минимально приемлемая сумма больше запрошенной.")
        if self.minimum_acceptable_term_months > self.profile.term_months:
            raise ValueError("Минимально приемлемый срок больше запрошенного.")
        return self


class SuggestedTerms(ApiModel):
    """Предлагаемые сумма и срок.

    Attributes:
        amount: Сумма кредита.
        term_months: Срок кредита в месяцах.
    """

    amount: int
    term_months: int


class RecoveredVariant(ApiModel):
    """Альтернативный вариант кредита.

    Attributes:
        product_id: Идентификатор кредитного продукта.
        suggested_terms: Предлагаемые условия кредита.
        risk_probability: Предварительная вероятность риска.
        risk_band: Категория риска.
        risk_change_vs_original: Изменение риска относительно исходной заявки.
        model_version: Версия модели скоринга.
        explanation: Пояснение альтернативы.
    """

    product_id: str
    suggested_terms: SuggestedTerms
    risk_probability: float = Field(ge=0, le=1)
    risk_band: str
    risk_change_vs_original: float
    model_version: str
    explanation: str


class RejectedProduct(ApiModel):
    """Продукт без подходящего альтернативного варианта.

    Attributes:
        product_id: Идентификатор кредитного продукта.
        reasons: Причины выбора или отказа.
    """

    product_id: str
    reasons: list[str]


class RecoveryResponse(ApiModel):
    """Результат поиска альтернатив.

    Attributes:
        case_id: Демонстрационный идентификатор заявки.
        variants: Альтернативные кредитные условия.
        unavailable_products: Продукты без подходящих условий.
        declined_reasons: Причины предыдущего отказа.
        estimate_type: Тип предварительной оценки.
    """

    case_id: str
    variants: list[RecoveredVariant]
    unavailable_products: list[RejectedProduct]
    declined_reasons: list[str]
    estimate_type: Literal["synthetic_risk_probability"] = "synthetic_risk_probability"
