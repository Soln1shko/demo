from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

Profile = Literal["retail", "production", "services"]


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    inn: str
    legal: str
    profile: str
    region: str
    age: int
    revenue: float
    expenses: float
    debt: float
    goal: str
    amount: float
    months: int
    frequency: str
    urgency: str
    collateral: str
    seasonality: str
    late: bool
    cash_balance: float | None
    cash_balance_at: datetime | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def monogram(self) -> str:
        import re

        cleaned = re.sub(r"^(ООО|ИП|АО|ПАО)\s*", "", self.name, flags=re.IGNORECASE)
        cleaned = re.sub(r"[«»\"']", "", cleaned).strip()
        return cleaned[:1].upper() or "К"


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    inn: str = Field(pattern=r"^\d{10}(\d{2})?$")
    legal: Literal["ooo", "ip"] = "ooo"
    profile: Profile = "retail"
    region: str = Field("", max_length=80)
    revenue: float = Field(ge=0)
    expenses: float = Field(ge=0)
    debt: float = Field(ge=0)
    age: int = Field(ge=0)


class OrganizationPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    profile: Profile | None = None
    region: str | None = Field(None, max_length=80)
    age: int | None = Field(None, ge=0)
    goal: str | None = Field(None, max_length=80)
    amount: float | None = Field(None, ge=50_000, le=150_000_000)
    months: int | None = Field(None, ge=1, le=120)
    frequency: Literal["once", "regular"] | None = None
    urgency: Literal["week", "month", "later"] | None = None
    collateral: Literal["no", "realty", "transport", "buying"] | None = None
    seasonality: Literal["stable", "seasonal"] | None = None


class FinancialsIn(BaseModel):
    revenue: float = Field(ge=0)
    expenses: float = Field(ge=0)
    debt: float = Field(ge=0)


class CashBalanceIn(BaseModel):
    amount: float = Field(ge=0)


class FinanceMonthIn(FinancialsIn):
    pass


class FinanceMonthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: str
    revenue: float
    expenses: float
    debt: float
    source: str


class OnboardingData(BaseModel):
    """Черновик анкеты. Все поля необязательны: клиент заполняет по шагам."""

    step: int | None = Field(None, ge=0, le=3)
    legal: Literal["ooo", "ip"] | None = None
    name: str | None = Field(None, max_length=100)
    inn: str | None = Field(None, max_length=12)
    region: str | None = Field(None, max_length=80)
    age: float | None = Field(None, ge=0)
    profile: Profile | None = None
    goal: str | None = Field(None, max_length=80)
    amount: float | None = None
    months: float | None = None
    frequency: Literal["once", "regular"] | None = None
    urgency: Literal["week", "month", "later"] | None = None
    collateral: Literal["no", "realty", "transport", "buying"] | None = None
    revenue: float | None = Field(None, ge=0)
    expenses: float | None = Field(None, ge=0)
    debt: float | None = Field(None, ge=0)
    seasonality: Literal["stable", "seasonal"] | None = None
    late: bool | None = None


class OnboardingOut(BaseModel):
    step: int
    data: dict[str, Any]


class LookupOut(BaseModel):
    inn: str
    legal: str
    name: str
    status: str
    status_text: str
    okved: dict[str, str]
    registered_at: str
    address: str
    head: str = ""
    source: str = ""
    demo: bool = False  # True — данные синтетические (нет ключа DaData), подставлять их в форму нельзя
