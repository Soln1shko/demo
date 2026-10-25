"""Документы: валидация загрузок, хранение, образцы."""

from __future__ import annotations

import hashlib
from pathlib import PurePath

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApiError, forbidden, not_found
from app.integrations.storage import get_storage
from app.models import Application, ApplicationDraft, Document, Organization, OrganizationMember, User
from app.models.user import BANK_ROLES

ALLOWED = {
    ".pdf": ("application/pdf", (b"%PDF",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG",)),
}
SAMPLE_MIME = "text/plain; charset=utf-8"


async def _attach_to_draft(session: AsyncSession, org_id: str, doc_id: str) -> None:
    draft = await session.get(ApplicationDraft, org_id)
    if draft is not None:
        data = dict(draft.data)
        data["document_ids"] = [*data.get("document_ids", []), doc_id]
        draft.data = data


async def _detach_from_draft(session: AsyncSession, org_id: str, doc_id: str) -> None:
    draft = await session.get(ApplicationDraft, org_id)
    if draft is not None:
        data = dict(draft.data)
        data["document_ids"] = [i for i in data.get("document_ids", []) if i != doc_id]
        draft.data = data


async def _target_app(
    session: AsyncSession, org: Organization, application_id: str | None
) -> Application | None:
    if not application_id:
        return None
    app = await session.get(Application, application_id)
    if app is None or app.organization_id != org.id:
        raise not_found("Заявка")
    if app.status != "needs_info":
        raise ApiError(409, "invalid_transition", "Документы можно добавлять только по запросу банка")
    return app


def _request_item_title(app: Application | None, item_id: str | None) -> str | None:
    """Название пункта запроса банка; ошибка, если такого пункта нет или он не про документ."""
    if not item_id:
        return None
    items = (app.info_request or {}).get("items", []) if app else []
    item = next((i for i in items if i["id"] == item_id and i["kind"] == "document"), None)
    if item is None:
        raise ApiError(
            422,
            "validation_failed",
            "Такого пункта запроса нет",
            errors=[{"field": "request_item", "message": "Неизвестный пункт"}],
        )
    return str(item["title"])


async def _drop_previous(session: AsyncSession, app: Application, item_id: str) -> None:
    """Новый файл на тот же пункт заменяет прежний: на один пункт — один документ."""
    old = (
        await session.execute(
            select(Document).where(Document.application_id == app.id, Document.request_item == item_id)
        )
    ).scalars()
    for d in old:
        if d.storage_key:
            await get_storage().delete(d.storage_key)
        await session.delete(d)


async def upload(
    session: AsyncSession,
    user: User,
    org: Organization,
    file: UploadFile,
    application_id: str | None,
    request_item: str | None = None,
) -> Document:
    ext = PurePath(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise ApiError(415, "unsupported_media_type", "Выберите PDF, JPG или PNG до 10 МБ")
    limit = get_settings().max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ApiError(413, "payload_too_large", "Файл больше 10 МБ")
    mime, signatures = ALLOWED[ext]
    if not data or not data.startswith(signatures):
        raise ApiError(415, "unsupported_media_type", "Содержимое файла не соответствует его расширению")
    app = await _target_app(session, org, application_id)
    _request_item_title(app, request_item)
    if app and request_item:
        await _drop_previous(session, app, request_item)
    doc = Document(
        organization_id=org.id, application_id=app.id if app else None, uploader_id=user.id,
        name=PurePath(file.filename or "document").name[:200], size=len(data), mime=mime, kind="upload",
        sha256=hashlib.sha256(data).hexdigest(), request_item=request_item if app else None,
    )  # fmt: skip
    doc.storage_key = f"{org.id}/{doc.id}{ext}"
    await get_storage().put(doc.storage_key, data, mime)
    session.add(doc)
    await session.flush()
    if app is None:
        await _attach_to_draft(session, org.id, doc.id)
    await session.commit()
    return doc


async def add_sample(
    session: AsyncSession,
    user: User,
    org: Organization,
    application_id: str | None,
    request_item: str | None = None,
) -> Document:
    app = await _target_app(session, org, application_id)
    title = _request_item_title(app, request_item)
    if app and request_item:
        await _drop_previous(session, app, request_item)
    if app:
        n = len((await session.execute(select(Document.id).where(Document.application_id == app.id))).all())
    else:
        draft = await session.get(ApplicationDraft, org.id)
        n = len(draft.data.get("document_ids", []) if draft else [])
    name = f"{title} · образец.pdf" if title else f"Выписка за 6 месяцев · образец {n + 1}.pdf"
    doc = Document(
        organization_id=org.id, application_id=app.id if app else None, uploader_id=user.id,
        name=name[:200], size=0, mime=SAMPLE_MIME, kind="sample", request_item=request_item if app else None,
    )  # fmt: skip
    session.add(doc)
    await session.flush()
    if app is None:
        await _attach_to_draft(session, org.id, doc.id)
    await session.commit()
    return doc


async def get_document(session: AsyncSession, user: User, doc_id: str) -> Document:
    doc = await session.get(Document, doc_id)
    if doc is None:
        raise not_found("Документ")
    if user.role in BANK_ROLES:
        return doc
    member = (
        await session.execute(
            select(OrganizationMember.id).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == doc.organization_id,
            )
        )
    ).first()
    if member is None:
        raise not_found("Документ")
    return doc


async def delete(session: AsyncSession, user: User, doc_id: str) -> None:
    doc = await get_document(session, user, doc_id)
    if user.role in BANK_ROLES:
        raise forbidden()
    if doc.application_id is not None:
        app = await session.get(Application, doc.application_id)
        # пока банк ждёт ответ, клиент может убрать или заменить документ, который сам приложил к пункту запроса
        if not (doc.request_item and app is not None and app.status == "needs_info"):
            raise ApiError(409, "document_locked", "Документ уже привязан к отправленной заявке")
    await _detach_from_draft(session, doc.organization_id, doc.id)
    if doc.storage_key:
        await get_storage().delete(doc.storage_key)
    await session.delete(doc)
    await session.commit()


async def read_content(doc: Document, org: Organization | None) -> tuple[bytes, str]:
    if doc.kind == "sample":
        revenue = f"{round(org.revenue):,}".replace(",", " ") if org else "2 400 000"
        expenses = f"{round(org.expenses):,}".replace(",", " ") if org else "1 750 000"
        text = (
            "СИНТЕТИЧЕСКИЙ ОБРАЗЕЦ. Не банковский документ.\n"
            f"{org.name if org else 'ООО Форма'}. Выручка за месяц: {revenue} руб. Расходы: {expenses} руб.\n"
        )
        return text.encode("utf-8"), SAMPLE_MIME
    assert doc.storage_key
    return await get_storage().get(doc.storage_key), doc.mime
