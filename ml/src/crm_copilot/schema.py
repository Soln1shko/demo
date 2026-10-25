"""Снимок CRM и черновик ответа с явными пробелами в данных."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.model import StrictModel
from document_parser.schema import CustomerProfile
from underwriting.schema import CheckSnapshot, SuppliedScoring, UnderwritingResponse


class ConversationMessage(StrictModel):
    """Сообщение из истории обращения.

    Attributes:
        message_id: Идентификатор сообщения.
        author: Автор сообщения.
        text: Текст сообщения или факта.
    """

    message_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    author: Literal["customer", "employee", "system"]
    text: str = Field(min_length=1, max_length=2000)


class ApplicationContext(StrictModel):
    """Данные заявки из CRM.

    Attributes:
        status: Статус проверки или заявки.
        product_id: Идентификатор кредитного продукта.
        requested_amount: Запрошенная сумма кредита.
        term_months: Срок кредита в месяцах.
        purpose: Цель кредита.
        decision: Выбранное сотрудником решение.
        decision_reason: Причина кредитного решения.
    """

    status: str | None = Field(default=None, max_length=80)
    product_id: str | None = Field(default=None, max_length=80)
    requested_amount: int | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, gt=0)
    purpose: str | None = Field(default=None, max_length=200)
    decision: Literal["approved", "declined", "pending"] | None = None
    decision_reason: str | None = Field(default=None, max_length=500)


class DocumentContext(StrictModel):
    """Состояние документа в CRM.

    Attributes:
        document_id: Идентификатор документа.
        label: Название поля или проверки.
        status: Статус проверки или заявки.
        details: Подробности проверки.
    """

    document_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    label: str = Field(min_length=1, max_length=120)
    status: Literal["missing", "uploaded", "reviewing", "verified", "rejected"]
    details: str | None = Field(default=None, max_length=500)


class VerifiedFact(StrictModel):
    """Подтверждённый факт из CRM.

    Attributes:
        fact_id: Идентификатор факта.
        text: Текст сообщения или факта.
        source: Источник сведения.
    """

    fact_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    text: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=200)


class RequiredField(StrictModel):
    """Данные, необходимые для ответа клиенту.

    Attributes:
        path: Путь к полю или файлу.
        label: Название поля или проверки.
        reason: Обоснование оценки или действия.
        obtain_from: Источник недостающих сведений.
        acceptable_values: Допустимые значения поля.
    """

    path: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=300)
    obtain_from: Literal["customer", "employee", "backend", "document", "check"]
    acceptable_values: list[str] = Field(default_factory=list, max_length=10)


class CopilotRequest(StrictModel):
    """Входной снимок обращения CRM.

    Attributes:
        case_id: Демонстрационный идентификатор заявки.
        customer_question: Вопрос клиента.
        history: История переписки.
        application: Данные кредитной заявки.
        profile: Профиль клиента или бизнеса.
        scoring: Полученные результаты скоринга.
        checks: Результаты проверок.
        documents: Документы для обработки или поиска.
        underwriting: Резюме заявки андеррайтинга.
        verified_facts: Подтверждённые сведения.
        required_fields: Поля, необходимые для однозначного ответа.
    """

    case_id: str = Field(pattern=r"^DEMO-[A-Z0-9-]{1,24}$")
    customer_question: str = Field(min_length=1, max_length=2000)
    history: list[ConversationMessage] = Field(default_factory=list, max_length=50)
    application: ApplicationContext | None = None
    profile: CustomerProfile | None = None
    scoring: SuppliedScoring | None = None
    checks: list[CheckSnapshot] = Field(default_factory=list, max_length=30)
    documents: list[DocumentContext] = Field(default_factory=list, max_length=30)
    underwriting: UnderwritingResponse | None = None
    verified_facts: list[VerifiedFact] = Field(default_factory=list, max_length=30)
    required_fields: list[RequiredField] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_ids(self) -> CopilotRequest:
        """Проверяет уникальность идентификаторов снимка.

        Returns:
            CopilotRequest: Проверенный снимок CRM.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        for items, key in (
            (self.history, "message_id"),
            (self.checks, "check_id"),
            (self.documents, "document_id"),
            (self.verified_facts, "fact_id"),
        ):
            if len({getattr(item, key) for item in items}) != len(items):
                raise ValueError(f"Повторяется {key} в снимке CRM.")
        if self.underwriting and self.underwriting.case_id != self.case_id:
            raise ValueError("Резюме андеррайтинга относится к другой заявке.")
        return self


class MissingDatum(StrictModel):
    """Недостающее сведение для ответа.

    Attributes:
        path: Путь к полю или файлу.
        label: Название поля или проверки.
        reason: Обоснование оценки или действия.
        obtain_from: Источник недостающих сведений.
    """

    path: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=300)
    obtain_from: Literal["customer", "employee", "backend", "document", "check"]


class NextAction(StrictModel):
    """Следующее действие сотрудника.

    Attributes:
        text: Текст сообщения или факта.
        evidence: Пути к подтверждающим полям.
    """

    text: str = Field(min_length=1, max_length=300)
    evidence: list[str] = Field(default_factory=list, max_length=5)


class GeneratedCopilot(StrictModel):
    """Черновик, сгенерированный LLM.

    Attributes:
        summary: Краткое резюме.
        summary_evidence: Источники фактов в резюме.
        missing_data: Недостающие сведения.
        next_actions: Рекомендуемые действия.
        reply_draft: Черновик ответа клиенту.
        reply_evidence: Источники фактов в черновике ответа.
    """

    summary: str = Field(min_length=1, max_length=800)
    summary_evidence: list[str] = Field(max_length=12)
    missing_data: list[MissingDatum] = Field(max_length=12)
    next_actions: list[NextAction] = Field(max_length=8)
    reply_draft: str = Field(min_length=1, max_length=1000)
    reply_evidence: list[str] = Field(max_length=12)


class CopilotResponse(StrictModel):
    """Проверенный ответ CRM-помощника.

    Attributes:
        case_id: Демонстрационный идентификатор заявки.
        answerability: Возможность однозначно ответить.
        summary: Краткое резюме.
        summary_evidence: Источники фактов в резюме.
        missing_data: Недостающие сведения.
        next_actions: Рекомендуемые действия.
        reply_draft: Черновик ответа клиенту.
        reply_evidence: Источники фактов в черновике ответа.
        requires_employee_confirmation: Необходимость подтверждения сотрудником.
        model: Название использованной LLM.
        synthetic: Признак демонстрационных данных.
    """

    case_id: str
    answerability: Literal["ready", "needs_data"]
    summary: str
    summary_evidence: list[str]
    missing_data: list[MissingDatum]
    next_actions: list[NextAction]
    reply_draft: str
    reply_evidence: list[str]
    requires_employee_confirmation: bool = True
    model: str
    synthetic: bool = True
