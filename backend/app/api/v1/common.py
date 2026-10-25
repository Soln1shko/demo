"""Общие зависимости роутеров."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Client, Session, get_user_org
from app.core.errors import ApiError
from app.models import Organization, User
from app.services import organizations as orgs


async def resolve_org(
    session: AsyncSession, user: User, organization_id: str | None, header_org: str | None
) -> Organization:
    org_id = organization_id or header_org
    if org_id:
        return await get_user_org(session, user, org_id)
    found = await orgs.list_orgs(session, user)
    if not found:
        raise ApiError(409, "onboarding_required", "Сначала заполните анкету компании")
    return found[0]


async def _org_dep(
    session: Session,
    user: Client,
    organization_id: Annotated[str | None, Query()] = None,
    x_organization_id: Annotated[str | None, Header()] = None,
) -> Organization:
    return await resolve_org(session, user, organization_id, x_organization_id)


async def _path_org(org_id: str, session: Session, user: Client) -> Organization:
    return await get_user_org(session, user, org_id)


CurrentOrg = Annotated[Organization, Depends(_org_dep)]
PathOrg = Annotated[Organization, Depends(_path_org)]
