from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import ProductOut


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    size: int
    mime: str
    kind: str
    application_id: str | None
    request_item: str | None = None
    created_at: datetime


class InfoItemOut(BaseModel):
    id: str
    kind: Literal["document", "data", "clarify"]
    title: str
    template_id: str | None = None


class InfoRequestOut(BaseModel):
    """Запрос банка: документы, данные и уточнения — разные пункты, на каждый нужен ответ."""

    requested_at: str
    message: str | None = None
    items: list[InfoItemOut]
    answers: dict[str, str] = Field(default_factory=dict)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    text: str
    actor_role: str
    at: datetime


class FactorOut(BaseModel):
    code: str
    title: str
    delta: int
    detail: str


class RiskOut(BaseModel):
    score: int
    load: float
    cash: float
    pay: float
    result: str
    alt: float
    factors: list[FactorOut]
    reasons: list[str]
    rules_version: int
    created_at: datetime
    approval_pct: int | None = None
    risk_band: str | None = None
    complexity: str | None = None
    priority: str | None = None


class CalcOut(BaseModel):
    interest: float
    cost: float
    total: float
    first: float
    last: float
    peak: float
    monthly: float
    rest_at_peak: float


class ApplicationOut(BaseModel):
    id: str
    organization_id: str
    status: str
    version: int
    product: ProductOut
    amount: float
    months: int
    days: int
    rate: float
    scheme: str
    fee: float
    goal: str
    company: str
    inn: str
    legal: str
    region: str
    revenue: float
    expenses: float
    debt: float
    age: int
    late: bool
    consent: bool
    assignee: str | None
    offer_amount: float | None
    original_amount: float | None
    comment: str | None
    manual_reason: str | None
    requested_doc_count: int | None
    info_request: InfoRequestOut | None = None
    created_at: datetime
    updated_at: datetime
    risk: RiskOut | None
    calc: CalcOut
    documents: list[DocumentOut]
    next_actions: list[str]


class DraftIn(BaseModel):
    product_id: str | None = None
    replace: bool = False
    step: int | None = Field(None, ge=1, le=3)
    amount: float | None = None
    months: int | None = None
    days: int | None = None
    rate: float | None = None
    scheme: str | None = None
    fee: float | None = None
    goal: str | None = Field(None, max_length=120)
    company: str | None = Field(None, max_length=120)
    inn: str | None = Field(None, max_length=12)
    legal: str | None = None
    region: str | None = None
    revenue: float | None = None
    expenses: float | None = None
    debt: float | None = None
    age: int | None = None
    late: bool | None = None
    consent: bool | None = None
    document_ids: list[str] | None = None


class DraftOut(BaseModel):
    product_id: str
    product: ProductOut
    step: int
    amount: float
    months: int
    days: int
    rate: float
    scheme: str
    fee: float
    goal: str
    company: str
    inn: str
    legal: str
    region: str
    revenue: float
    expenses: float
    debt: float
    age: int
    late: bool
    consent: bool
    documents: list[DocumentOut]
    updated_at: datetime


class SubmitIn(BaseModel):
    organization_id: str
    consent: bool
    document_ids: list[str] | None = None


class SupplementIn(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)  # ответы на пункты «данные» и «уточнение»
    comment: str | None = Field(None, max_length=500)
    version: int | None = None


class SignIn(BaseModel):
    agreed: bool
    version: int | None = None


class VersionIn(BaseModel):
    version: int | None = None


class ContractOut(BaseModel):
    company: str
    product_name: str
    amount: float
    rate: float
    scheme: str
    daily: bool
    days: int
    months: int
    total: float
    cost: float
    peak: float
    first: float
    fee: float
    note: str


class TransitionIn(BaseModel):
    """Совместимость с проектным контрактом: единая точка переходов."""

    action: str
    version: int | None = None
    reason: str | None = None


class ExportOut(BaseModel):
    application: dict[str, Any]
    events: list[dict[str, Any]]
