"""Черновик заявки и её отправка."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApiError, not_found, validation
from app.core.events import bus
from app.db.base import utcnow
from app.domain.finance import QuoteInput, quote_error
from app.models import Application, ApplicationDraft, Document, Organization, User
from app.schemas.application import DocumentOut, DraftIn, DraftOut
from app.services import applications as apps
from app.services.catalog import get_product, product_out, product_spec, snapshot

DRAFT_FIELDS = (
    "amount", "months", "days", "rate", "scheme", "fee", "goal", "company", "inn", "legal", "region",
    "revenue", "expenses", "debt", "age", "late", "consent", "document_ids",
)  # fmt: skip
INN_RE = re.compile(r"^\d{10}(\d{2})?$")


def _bounded(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _defaults(org: Organization, product) -> dict[str, Any]:  # noqa: ANN001
    return {
        "amount": _bounded(org.amount or 1_000_000, product.min_amount, product.max_amount),
        "months": int(_bounded(org.months or 24, product.min_months, product.max_months)),
        "days": 30,
        "rate": product.daily if product.daily is not None else product.rate,
        "scheme": product.scheme,
        "fee": 0.0,
        "goal": "" if org.goal in ("", "Пока изучаю возможности") else org.goal,
        "company": org.name, "inn": org.inn, "legal": org.legal, "region": org.region,
        "revenue": org.revenue, "expenses": org.expenses, "debt": org.debt, "age": org.age,
        "late": org.late, "consent": False, "document_ids": [],
    }  # fmt: skip


async def get_draft_row(session: AsyncSession, org_id: str) -> ApplicationDraft | None:
    return await session.get(ApplicationDraft, org_id)


async def draft_out(session: AsyncSession, row: ApplicationDraft) -> DraftOut:
    product = await get_product(session, row.product_id)
    data = dict(row.data)
    ids = data.get("document_ids", [])
    docs = []
    if ids:
        found = {
            d.id: d
            for d in (await session.execute(select(Document).where(Document.id.in_(ids)))).scalars()
            if d.application_id is None
        }
        docs = [DocumentOut.model_validate(found[i]) for i in ids if i in found]
    return DraftOut(
        product_id=row.product_id, product=product_out(product), step=row.step, documents=docs,
        updated_at=row.updated_at, **{k: data[k] for k in DRAFT_FIELDS if k != "document_ids"},
    )  # fmt: skip


async def upsert_draft(session: AsyncSession, org: Organization, body: DraftIn) -> ApplicationDraft:
    row = await get_draft_row(session, org.id)
    product_id = body.product_id or (row.product_id if row else None)
    if product_id is None:
        raise validation("Укажите продукт для черновика", "product_id")
    product = await get_product(session, product_id)
    if not product.calculable:
        raise validation("Заявка по этому продукту пока недоступна", "product_id")
    fresh = row is None or body.replace or row.product_id != product_id
    changes = body.model_dump(exclude_unset=True, exclude={"product_id", "replace", "step"})
    if fresh:
        data = _defaults(org, product)
        step = body.step or 1
    else:
        assert row is not None
        data = dict(row.data)
        step = body.step or row.step
    data.update({k: v for k, v in changes.items() if v is not None})
    if row is None:
        row = ApplicationDraft(organization_id=org.id, product_id=product_id, step=step, data=data)
        session.add(row)
    else:
        row.product_id, row.step, row.data, row.updated_at = product_id, step, data, utcnow()
    await session.commit()
    return row


async def delete_draft(session: AsyncSession, org_id: str) -> None:
    row = await get_draft_row(session, org_id)
    if row:
        await session.delete(row)
        await session.commit()


def validate_draft(data: dict[str, Any], doc_count: int, consent: bool) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    def bad(field: str, message: str) -> None:
        errors.append({"field": field, "message": message})

    if not str(data.get("goal", "")).strip():
        bad("goal", "Укажите цель финансирования.")
    if not str(data.get("company", "")).strip() or not INN_RE.match(str(data.get("inn", ""))):
        bad("company", "Проверьте название и ИНН (10 или 12 цифр).")
    nums = [data.get(k) for k in ("revenue", "expenses", "debt", "age")]
    if not all(isinstance(n, int | float) for n in nums):
        bad("finance", "Заполните финансовые показатели.")
    elif data["revenue"] <= 0 or data["expenses"] < 0 or data["debt"] < 0 or data["age"] < 0:
        bad("finance", "Выручка должна быть больше нуля, остальные показатели — не меньше нуля.")
    if doc_count < 1:
        bad("documents", "Прикрепите файл или добавьте демонстрационный документ.")
    if not consent:
        bad("consent", "Подтвердите данные и согласие на рассмотрение заявки.")
    return errors


async def submit(
    session: AsyncSession, user: User, org: Organization, consent: bool, extra_ids: list[str] | None
) -> Application:
    row = await get_draft_row(session, org.id)
    if row is None:
        raise not_found("Черновик заявки")
    product = await get_product(session, row.product_id)
    spec = product_spec(product)
    data = dict(row.data)
    ids = list(dict.fromkeys([*data.get("document_ids", []), *(extra_ids or [])]))
    docs = list(
        (
            await session.execute(
                select(Document).where(
                    Document.id.in_(ids),
                    Document.organization_id == org.id,
                    Document.application_id.is_(None),
                )
            )
        ).scalars()
    )
    errors = validate_draft(data, len(docs), consent)
    quote_input = QuoteInput(
        data["amount"], data["months"], data["days"], data["rate"], data["scheme"], data["fee"]
    )
    if (msg := quote_error(spec, quote_input)) is not None:
        errors.append({"field": "amount", "message": msg})
    if errors:
        raise ApiError(422, "validation_failed", errors[0]["message"], errors=errors)

    app = Application(
        id=apps.new_app_id(), organization_id=org.id, product_id=product.id, status="submitted", version=1,
        amount=data["amount"], months=data["months"], days=data["days"], rate=data["rate"], scheme=data["scheme"],
        fee=data["fee"], goal=data["goal"].strip(), company=data["company"].strip(), inn=data["inn"],
        legal=data.get("legal", "ooo"), region=data.get("region", ""), revenue=data["revenue"],
        expenses=data["expenses"], debt=data["debt"], age=int(data["age"]), late=bool(data["late"]),
        consent=True, product_snapshot=snapshot(product),
    )  # fmt: skip
    session.add(app)
    await session.flush()
    for d in docs:
        d.application_id = app.id
    await session.delete(row)
    await apps.add_event(
        session, app.id, "submitted", "Заявка отправлена клиентом", actor=user, role="client"
    )
    await session.commit()
    await bus.publish(
        "application.created", {"id": app.id, "company": app.company, "amount": app.amount}, bank=True
    )
    await apps.publish_update(app)
    if get_settings().auto_check_on_submit:
        from app.workers.dispatcher import start_check

        await start_check(session, app, None)
    return app
