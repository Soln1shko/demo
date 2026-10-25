"""FastAPI-зависимости: текущий пользователь, роли, доступ к организации."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, forbidden, not_found
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import Organization, OrganizationMember, User
from app.models.user import BANK_ROLES, ROLE_ADMIN, ROLE_CLIENT

bearer = HTTPBearer(auto_error=False)
Session = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: Session, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], request: Request
) -> User:
    token = creds.credentials if creds else request.query_params.get("access_token")
    if not token:
        raise ApiError(401, "not_authenticated", "Требуется авторизация")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise ApiError(401, "invalid_token", "Сессия истекла или недействительна") from exc
    user = await session.get(User, payload["sub"])
    if user is None:
        raise ApiError(401, "invalid_token", "Пользователь не найден")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_client(user: CurrentUser) -> User:
    if user.role != ROLE_CLIENT:
        raise forbidden("Доступно только клиентам")
    return user


async def require_bank(user: CurrentUser) -> User:
    if user.role not in BANK_ROLES:
        raise forbidden("Доступно только сотрудникам банка")
    return user


async def require_admin(user: CurrentUser) -> User:
    if user.role != ROLE_ADMIN:
        raise forbidden("Доступно только администратору банка")
    return user


Client = Annotated[User, Depends(require_client)]
Bank = Annotated[User, Depends(require_bank)]
Admin = Annotated[User, Depends(require_admin)]


async def get_user_org(session: AsyncSession, user: User, org_id: str) -> Organization:
    """Организация, к которой у пользователя есть доступ. Чужая выглядит как несуществующая."""
    stmt = (
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(Organization.id == org_id, OrganizationMember.user_id == user.id)
    )
    org = (await session.execute(stmt)).scalar_one_or_none()
    if org is None:
        raise not_found("Организация")
    return org
