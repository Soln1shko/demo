from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    short: Mapped[str] = mapped_column(String(120))
    desc: Mapped[str] = mapped_column(String(400))
    icon: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(16))  # loan | line | overdraft | daily
    scheme: Mapped[str] = mapped_column(String(16))  # annuity | diff | bullet
    secured: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(16))  # working | gap | investment
    min_amount: Mapped[float] = mapped_column(Float)
    max_amount: Mapped[float] = mapped_column(Float)
    min_months: Mapped[int] = mapped_column(Integer)
    max_months: Mapped[int] = mapped_column(Integer)
    min_age: Mapped[int] = mapped_column(Integer, default=0)
    rate: Mapped[float] = mapped_column(Float)
    daily: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_label: Mapped[str] = mapped_column(String(60))
    discount: Mapped[str] = mapped_column(String(500))
    term: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str] = mapped_column(String(120))
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Поля справочника `data/Кредитные_продукты_Альфа_Банка_МСБ.csv` (id продуктов общие с ML)
    segment: Mapped[str] = mapped_column(String(16), default="msb")
    family: Mapped[str] = mapped_column(String(40), default="")
    purpose_tags: Mapped[list[str] | None] = mapped_column(JSON, default=list, nullable=True)
    pricing_type: Mapped[str] = mapped_column(String(32), default="")
    collateral_policy: Mapped[str] = mapped_column(String(24), default="")
    new_business_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    marketplace_required: Mapped[bool] = mapped_column(Boolean, default=False)
    effective_at: Mapped[str] = mapped_column(String(10), default="")
    # False — продукт есть в справочнике, но ставок для расчёта нет: калькулятор и заявка недоступны
    calculable: Mapped[bool] = mapped_column(Boolean, default=True)


class BankProduct(Base):
    """Некредитные продукты банка (справочник `Продукты_Альфа_Банка_вне_кредитов_МСБ.csv`)."""

    __tablename__ = "bank_products"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    segment: Mapped[str] = mapped_column(String(16))
    family: Mapped[str] = mapped_column(String(40))
    purpose_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    eligibility_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_url: Mapped[str] = mapped_column(String(160))
    effective_at: Mapped[str] = mapped_column(String(10))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class FeedItem(Base):
    __tablename__ = "feed_items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), default="editorial")
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(600))
    icon: Mapped[str] = mapped_column(String(40), default="radio")
    cta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class FeedDismissal(Base):
    __tablename__ = "feed_dismissals"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(String(80), primary_key=True)


class Setting(Base):
    """Key-value хранилище (например, версионированные правила скоринга)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
