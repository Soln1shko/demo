from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.application import ApplicationOut, EventOut


class BankRowOut(BaseModel):
    id: str
    company: str
    inn: str
    amount: float
    months: int
    product_id: str
    product_name: str
    status: str
    assignee: str | None
    score: int | None
    approval_pct: int | None = None
    complexity: str | None = None
    priority: str | None = None
    # Аналитик уже зафиксировал своё решение. Автоматическое решение системы — False.
    operator_decided: bool = False
    created_at: datetime
    hours_in_queue: int


class BankListOut(BaseModel):
    items: list[BankRowOut]
    total: int
    limit: int
    offset: int


class BankStatsOut(BaseModel):
    all: int
    # Рабочие корзины очереди, а не сырые статусы.
    inbox: int = 0
    fresh: int = 0
    system: int = 0
    waiting: int = 0
    done: int = 0
    submitted: int
    checking: int
    review: int
    needs_info: int
    approved: int
    alternative: int
    rejected: int
    signed: int
    funded: int
    withdrawn: int


class ExternalCheckOut(BaseModel):
    source: str
    status: str
    payload: dict[str, Any]
    at: datetime


class ChecklistItem(BaseModel):
    key: str
    checked: bool
    by: str | None = None


class BankDetailOut(BaseModel):
    application: ApplicationOut
    external_checks: list[ExternalCheckOut]
    checklist: list[ChecklistItem]
    note: str
    summary: str
    history: list[EventOut]


class RequestItemIn(BaseModel):
    kind: Literal["document", "data", "clarify"]
    title: str = Field(min_length=1, max_length=200)
    template_id: str | None = None


class RequestInfoIn(BaseModel):
    """Один запрос — сколько угодно пунктов. Поле `text` оставлено для старых клиентов API."""

    items: list[RequestItemIn] = Field(default_factory=list, max_length=12)
    message: str | None = Field(None, max_length=500)
    text: str | None = Field(None, max_length=500)
    template_id: str | None = None
    version: int | None = None


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected", "alternative"]
    reason: str = Field(min_length=10, max_length=1000)
    offer_amount: float | None = Field(None, gt=0)
    version: int | None = None


class ChecklistIn(BaseModel):
    key: Literal["numbers", "debt", "collateral"]
    checked: bool


class NoteIn(BaseModel):
    text: str = Field("", max_length=2000)


class AssignIn(BaseModel):
    assignee_id: str | None = None


class AssignBulkIn(BaseModel):
    application_ids: list[str] = Field(min_length=1, max_length=100)


class CheckStepOut(BaseModel):
    key: str
    label: str
    status: str  # pending | running | done
    at: datetime | None = None


class CheckRunOut(BaseModel):
    id: str
    application_id: str
    status: str
    result: str | None
    steps: list[CheckStepOut]
    started_at: datetime
    finished_at: datetime | None


class ScoringOut(BaseModel):
    score: int
    load: float
    cash: float
    pay: float
    result: str
    alt: float
    factors: list[dict[str, Any]]
    reasons: list[str]
    rules_version: int
    created_at: datetime


class RequestTemplate(BaseModel):
    id: str
    kind: Literal["document", "data", "clarify"]
    title: str
    text: str  # то же, что title (совместимость со старым клиентом)


class DemoScenarioIn(BaseModel):
    kind: Literal["good", "alt", "manual", "bad"]


class AuditOut(BaseModel):
    items: list[dict[str, Any]]
    total: int


class AuditVerifyOut(BaseModel):
    ok: bool
    checked: int
    broken_at: int | None = None
