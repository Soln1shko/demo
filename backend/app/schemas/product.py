from typing import Literal

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    id: str
    name: str
    short: str
    desc: str
    icon: str
    kind: str
    scheme: str
    secured: bool
    category: str
    min_amount: float
    max_amount: float
    min_months: int
    max_months: int
    min_age: int
    rate: float
    daily: float | None
    rate_label: str
    discount: str
    term: str
    source_url: str
    features: list[str]
    calculable: bool = True
    segment: str = "msb"
    family: str = ""
    purpose_tags: list[str] = []
    pricing_type: str = ""
    collateral_policy: str = ""
    new_business_allowed: bool = False
    marketplace_required: bool = False


class BankProductOut(BaseModel):
    id: str
    name: str
    segment: str
    family: str
    purpose_tags: list[str]
    eligibility_tags: list[str]
    source_url: str
    effective_at: str


class MatchOut(BaseModel):
    score: int
    reasons: list[str]
    warnings: list[str]


class ProductWithMatch(ProductOut):
    match: MatchOut | None = None


class MatchIn(BaseModel):
    organization_id: str
    goal: str = ""
    amount: float = Field(1_000_000, ge=0)
    months: int = Field(24, ge=1)
    collateral: Literal["no", "realty", "transport", "buying"] = "no"
    frequency: Literal["once", "regular"] = "once"


class MatchItem(BaseModel):
    product_id: str
    match: MatchOut


class QuoteIn(BaseModel):
    amount: float
    months: int | None = None
    days: int | None = None
    rate: float | None = None
    scheme: Literal["annuity", "diff", "bullet"] | None = None
    fee: float = Field(0, ge=0)
    stress_pct: float = Field(0, ge=-100, le=100)
    organization_id: str | None = None
    monthly_revenue: float | None = None
    net_margin_percent: float | None = None
    debt_to_revenue_ratio: float | None = None
    has_overdue_debt: bool | None = None
    credit_history_score: int | None = Field(None, ge=0, le=1000)
    has_collateral: bool | None = None
    legal_form: str | None = None
    business_age_months: int | None = None


class ScheduleRowOut(BaseModel):
    n: int
    payment: float
    principal: float
    interest: float
    balance: float


class QuoteOut(BaseModel):
    error: str | None = None
    interest: float = 0
    cost: float = 0
    total: float = 0
    first: float = 0
    last: float = 0
    peak: float = 0
    monthly: float = 0
    rest_at_peak: float | None = None
    scheme: str = "annuity"
    note: str = ""
    approval_pct: int | None = None
    risk_band: str | None = None


class ScheduleOut(BaseModel):
    unit: str
    interest: float
    rows: list[ScheduleRowOut]


class CompareItemIn(QuoteIn):
    product_id: str


class CompareIn(BaseModel):
    items: list[CompareItemIn] = Field(min_length=2, max_length=3)


class CompareRow(BaseModel):
    product_id: str
    name: str
    amount: float
    months: int
    days: int
    rate: float
    secured: bool
    daily: bool
    interest: float
    peak: float
    cost: float
    error: str | None = None
