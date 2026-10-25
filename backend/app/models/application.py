from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, new_id, utcnow


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    status: Mapped[str] = mapped_column(String(16), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    amount: Mapped[float] = mapped_column(Float)
    months: Mapped[int] = mapped_column(Integer)
    days: Mapped[int] = mapped_column(Integer, default=30)
    rate: Mapped[float] = mapped_column(Float)
    scheme: Mapped[str] = mapped_column(String(16))
    fee: Mapped[float] = mapped_column(Float, default=0)
    goal: Mapped[str] = mapped_column(String(120), default="")

    company: Mapped[str] = mapped_column(String(120))
    inn: Mapped[str] = mapped_column(String(12), index=True)
    legal: Mapped[str] = mapped_column(String(8), default="ooo")
    region: Mapped[str] = mapped_column(String(80), default="")
    revenue: Mapped[float] = mapped_column(Float)
    expenses: Mapped[float] = mapped_column(Float)
    debt: Mapped[float] = mapped_column(Float)
    age: Mapped[int] = mapped_column(Integer)
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)

    assignee: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    offer_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_doc_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Последний запрос банка: {requested_at, message, items: [{id, kind, title, template_id}], answers: {item_id: text}}
    info_request: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class ApplicationEvent(Base):
    """Append-only журнал с хеш-цепочкой (подмена записей обнаруживается проверкой)."""

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(20), default="system")
    type: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64), default="")
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    uploader_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(Integer, default=0)
    mime: Mapped[str] = mapped_column(String(60), default="application/pdf")
    kind: Mapped[str] = mapped_column(String(10), default="upload")  # upload | sample
    request_item: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # пункт запроса банка, который закрывает документ
    storage_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    load: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    pay: Mapped[float] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(16))
    alt: Mapped[float] = mapped_column(Float, default=0)
    explanation: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    rules_version: Mapped[int] = mapped_column(Integer, default=1)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ExternalCheck(Base):
    __tablename__ = "external_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(12))  # fns | bki
    status: Mapped[str] = mapped_column(String(12), default="ok")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CheckRun(Base):
    __tablename__ = "check_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="running")  # running | done | failed
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class ReviewCheck(Base):
    __tablename__ = "review_checks"

    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(20), primary_key=True)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer, default=200)
    response: Mapped[Any] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
