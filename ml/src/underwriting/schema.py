"""Контракт снимка заявки и структурированного ответа аналитического помощника."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.model import StrictModel


class BusinessSnapshot(StrictModel):
    """Сведения о бизнесе в заявке.

    Attributes:
        segment: Сегмент микробизнеса или малого бизнеса.
        legal_form: Организационно-правовая форма.
        business_age_months: Возраст бизнеса в месяцах.
        industry: Отрасль бизнеса.
    """

    segment: Literal["micro", "small"]
    legal_form: Literal["ip", "ooo"]
    business_age_months: int = Field(ge=0)
    industry: str = Field(min_length=1, max_length=100)


class LoanApplication(StrictModel):
    """Условия запрошенного кредита.

    Attributes:
        product_id: Идентификатор кредитного продукта.
        requested_amount: Запрошенная сумма кредита.
        term_months: Срок кредита в месяцах.
        purpose: Цель кредита.
    """

    product_id: str = Field(min_length=1, max_length=80)
    requested_amount: int = Field(gt=0)
    term_months: int = Field(gt=0)
    purpose: str = Field(min_length=1, max_length=200)


class FinancialSnapshot(StrictModel):
    """Финансовые показатели бизнеса.

    Attributes:
        monthly_revenue: Месячная выручка.
        net_margin_percent: Чистая маржа в процентах.
        debt_to_revenue_ratio: Отношение долга к выручке.
    """

    monthly_revenue: int = Field(ge=0)
    net_margin_percent: float = Field(ge=0, le=100)
    debt_to_revenue_ratio: float = Field(ge=0)


class ScoringFactor(StrictModel):
    """Фактор скоринговой оценки.

    Attributes:
        feature: Название признака модели.
        contribution: Вклад фактора в логит риска.
    """

    feature: str = Field(min_length=1, max_length=100)
    contribution: float


class SuppliedScoring(StrictModel):
    """Полученный от бэка результат скоринга.

    Attributes:
        risk_probability: Предварительная вероятность риска.
        risk_band: Категория риска.
        factors: Вклады факторов модели.
        model_version: Версия модели скоринга.
    """

    risk_probability: float = Field(ge=0, le=1)
    risk_band: str = Field(min_length=1, max_length=40)
    factors: list[ScoringFactor] = Field(default_factory=list, max_length=20)
    model_version: str = Field(min_length=1, max_length=80)


class CheckSnapshot(StrictModel):
    """Результат отдельной проверки.

    Attributes:
        check_id: Идентификатор проверки.
        label: Название поля или проверки.
        status: Статус проверки или заявки.
        details: Подробности проверки.
        source: Источник сведения.
    """

    check_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str = Field(min_length=1, max_length=100)
    status: Literal["clear", "flag", "missing"]
    details: str = Field(max_length=500)
    source: str = Field(min_length=1, max_length=100)


class AdditionalFact(StrictModel):
    """Дополнительный факт из документа.

    Attributes:
        fact_id: Идентификатор факта.
        value: Значение факта или признака.
        source: Источник сведения.
    """

    fact_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    value: str | int | float | bool
    source: str = Field(min_length=1, max_length=100)


class UnderwritingRequest(StrictModel):
    """Полученный от бэка снимок; скоринг здесь никогда не пересчитывается.

    Attributes:
        case_id: Заявки идентификатор.
        business: Бизнеса.
        application: Заявка.
        financials: Финансовые показатели.
        scoring: Скоринг.
        checks: Проверки.
        additional_facts: Дополнительные факты.
    """

    case_id: str = Field(pattern=r"^DEMO-[A-Z0-9-]{1,24}$")
    business: BusinessSnapshot
    application: LoanApplication
    financials: FinancialSnapshot
    scoring: SuppliedScoring
    checks: list[CheckSnapshot] = Field(default_factory=list, max_length=20)
    additional_facts: list[AdditionalFact] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_ids(self) -> UnderwritingRequest:
        """Проверяет уникальность идентификаторов снимка.

        Returns:
            UnderwritingRequest: Проверенный снимок заявки.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        if len({item.check_id for item in self.checks}) != len(self.checks):
            raise ValueError("check_id в снимке заявки должны быть уникальны.")
        if len({item.fact_id for item in self.additional_facts}) != len(self.additional_facts):
            raise ValueError("fact_id в снимке заявки должны быть уникальны.")
        return self


class Finding(StrictModel):
    """Вывод с подтверждающими полями.

    Attributes:
        text: Текст сообщения или факта.
        evidence: Пути к подтверждающим полям.
    """

    text: str = Field(min_length=1, max_length=400)
    evidence: list[str] = Field(min_length=1, max_length=5)


class GeneratedAssessment(StrictModel):
    """Сгенерированные LLM выводы по заявке.

    Attributes:
        summary: Краткое резюме.
        evidence: Пути к подтверждающим полям.
        strengths: Сильные стороны заявки.
        risks: Риски заявки.
        missing_data: Недостающие сведения.
        next_actions: Рекомендуемые действия.
    """

    summary: str = Field(min_length=1, max_length=800)
    evidence: list[str] = Field(min_length=1, max_length=30)
    strengths: list[Finding] = Field(max_length=6)
    risks: list[Finding] = Field(max_length=6)
    missing_data: list[Finding] = Field(max_length=6)
    next_actions: list[Finding] = Field(max_length=6)


class OverallAssessment(StrictModel):
    """Общая оценка заявки.

    Attributes:
        level: Уровень оценки или классификации.
        summary: Краткое резюме.
        evidence: Пути к подтверждающим полям.
    """

    level: Literal["positive", "mixed", "concerning", "insufficient_data"]
    summary: str
    evidence: list[str]


class Classification(StrictModel):
    """Сложность ручного решения.

    Attributes:
        level: Уровень оценки или классификации.
        reason: Обоснование оценки или действия.
        evidence: Пути к подтверждающим полям.
    """

    level: Literal["low", "medium", "high"]
    reason: str
    evidence: list[str]


class PriorityClassification(Classification):
    """Приоритет кейса для аналитика.

    Attributes:
        exposure_months: Сумма кредита в месяцах выручки.
        business_segment: Масштаб бизнеса.
    """

    exposure_months: float | None
    business_segment: Literal["micro", "small"]


class UnderwritingResponse(StrictModel):
    """Проверенное резюме заявки.

    Attributes:
        case_id: Демонстрационный идентификатор заявки.
        overall_assessment: Общая оценка заявки.
        strengths: Сильные стороны заявки.
        risks: Риски заявки.
        missing_data: Недостающие сведения.
        next_actions: Рекомендуемые действия.
        decision_complexity: Сложность ручного решения.
        analyst_priority: Приоритет заявки для аналитика.
        scoring_model_version: Версия скоринговой модели.
        model: Название использованной LLM.
        synthetic: Признак демонстрационных данных.
    """

    case_id: str
    overall_assessment: OverallAssessment
    strengths: list[Finding]
    risks: list[Finding]
    missing_data: list[Finding]
    next_actions: list[Finding]
    decision_complexity: Classification
    analyst_priority: PriorityClassification
    scoring_model_version: str
    model: str
    synthetic: bool = True
