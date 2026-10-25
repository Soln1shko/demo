from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import Client, CurrentUser, Session, get_user_org
from app.core.errors import not_found
from app.models import Document, Organization
from app.models.user import BANK_ROLES
from app.schemas.application import DocumentOut
from app.services import documents as svc

router = APIRouter(prefix="/documents", tags=["documents"])


class SampleIn(BaseModel):
    organization_id: str
    application_id: str | None = None
    request_item: str | None = None


@router.post("", response_model=DocumentOut, status_code=201)
async def upload(
    session: Session,
    user: Client,
    file: Annotated[UploadFile, File()],
    organization_id: Annotated[str, Form()],
    application_id: Annotated[str | None, Form()] = None,
    request_item: Annotated[str | None, Form()] = None,
):
    org = await get_user_org(session, user, organization_id)
    return await svc.upload(session, user, org, file, application_id, request_item)


@router.post("/sample", response_model=DocumentOut, status_code=201)
async def sample(body: SampleIn, session: Session, user: Client):
    org = await get_user_org(session, user, body.organization_id)
    return await svc.add_sample(session, user, org, body.application_id, body.request_item)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    session: Session, user: CurrentUser, organization_id: str | None = None, application_id: str | None = None
):
    stmt = select(Document).order_by(Document.created_at.desc())
    if user.role in BANK_ROLES:
        if application_id:
            stmt = stmt.where(Document.application_id == application_id)
        if organization_id:
            stmt = stmt.where(Document.organization_id == organization_id)
    else:
        if not organization_id:
            raise not_found("Организация")
        org = await get_user_org(session, user, organization_id)
        stmt = stmt.where(Document.organization_id == org.id)
        if application_id:
            stmt = stmt.where(Document.application_id == application_id)
    return list((await session.execute(stmt)).scalars())


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: str, session: Session, user: CurrentUser):
    return await svc.get_document(session, user, doc_id)


@router.get("/{doc_id}/download")
async def download(doc_id: str, session: Session, user: CurrentUser):
    doc = await svc.get_document(session, user, doc_id)
    org = await session.get(Organization, doc.organization_id)
    content, mime = await svc.read_content(doc, org)
    return Response(
        content, media_type=mime,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.name)}", "X-Content-Type-Options": "nosniff"},
    )  # fmt: skip


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, session: Session, user: Client):
    await svc.delete(session, user, doc_id)
    return Response(status_code=204)
