from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, new_id, utcnow


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    inn: Mapped[str] = mapped_column(String(12), index=True)
    legal: Mapped[str] = mapped_column(String(8), default="ooo")  # ooo | ip
    profile: Mapped[str] = mapped_column(String(16), default="retail")  # retail | production | services
    region: Mapped[str] = mapped_column(String(80), default="")
    age: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0)
    expenses: Mapped[float] = mapped_column(Float, default=0)
    debt: Mapped[float] = mapped_column(Float, default=0)
    goal: Mapped[str] = mapped_column(String(80), default="")
    amount: Mapped[float] = mapped_column(Float, default=1_000_000)
    months: Mapped[int] = mapped_column(Integer, default=24)
    frequency: Mapped[str] = mapped_column(String(16), default="once")
    urgency: Mapped[str] = mapped_column(String(16), default="month")
    collateral: Mapped[str] = mapped_column(String(16), default="no")
    seasonality: Mapped[str] = mapped_column(String(16), default="stable")
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    cash_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_balance_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("user_id", "organization_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), default="owner")


class FinanceMonth(Base):
    __tablename__ = "finance_months"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    month: Mapped[str] = mapped_column(String(7), primary_key=True)  # YYYY-MM
    revenue: Mapped[float] = mapped_column(Float)
    expenses: Mapped[float] = mapped_column(Float)
    debt: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="Месячный отчет")


class OnboardingDraft(Base):
    __tablename__ = "onboarding_drafts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    step: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class ApplicationDraft(Base):
    __tablename__ = "application_drafts"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[str] = mapped_column(String(32))
    step: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
