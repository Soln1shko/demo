"""Аутентификация: регистрация, вход, ротация refresh-токенов."""

from __future__ import annotations

from datetime import timedelta

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApiError, conflict
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.db.base import utcnow
from app.models import RefreshToken, User
from app.models.user import BANK_ROLES, ROLE_CLIENT
from app.schemas.auth import RegisterIn, TokenOut, UserOut
from app.schemas.organization import OrganizationOut
from app.services import organizations as orgs

COOKIE = "refresh_token"
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("not-a-real-password")
    return _DUMMY_HASH


async def user_out(session: AsyncSession, user: User) -> UserOut:
    organizations = await orgs.list_orgs(session, user)
    return UserOut(
        id=user.id, name=user.name, email=user.email, role=user.role, operator_id=user.operator_id,
        onboarding_complete=bool(organizations) or user.role in BANK_ROLES,
        organizations=[OrganizationOut.model_validate(o) for o in organizations],
    )  # fmt: skip


async def register(session: AsyncSession, body: RegisterIn) -> User:
    email = body.email.strip().lower()
    if (await session.execute(select(User.id).where(User.email == email))).first():
        raise conflict(
            "email_taken", "Аккаунт с таким адресом уже существует. Войдите или используйте другой адрес."
        )
    user = User(
        email=email, name=body.name.strip(), password_hash=hash_password(body.password),
        role=ROLE_CLIENT, demo_consent=body.demo_consent,
    )  # fmt: skip
    session.add(user)
    await session.commit()
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = (
        await session.execute(select(User).where(User.email == email.strip().lower()))
    ).scalar_one_or_none()
    ok = verify_password(user.password_hash if user else _dummy_hash(), password)
    if user is None or not ok or user.role != ROLE_CLIENT:
        raise ApiError(401, "bad_credentials", "Неверный адрес или пароль")
    return user


async def authenticate_operator(session: AsyncSession, operator_id: str, password: str) -> User:
    user = (
        await session.execute(select(User).where(User.operator_id == operator_id.strip().lower()))
    ).scalar_one_or_none()
    ok = verify_password(user.password_hash if user else _dummy_hash(), password)
    if user is None or not ok or user.role not in BANK_ROLES:
        raise ApiError(401, "bad_credentials", "Неверный логин или пароль")
    return user


async def issue_tokens(session: AsyncSession, user: User, response: Response) -> TokenOut:
    settings = get_settings()
    raw, hashed = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=utcnow() + timedelta(days=settings.refresh_ttl_days),
        )
    )
    await session.commit()
    response.set_cookie(
        COOKIE, raw, max_age=settings.refresh_ttl_days * 86400, httponly=True, samesite="lax",
        secure=settings.cookie_secure, path=f"{settings.api_prefix}/auth",
    )  # fmt: skip
    return TokenOut(access_token=create_access_token(user.id, user.role), user=await user_out(session, user))


async def refresh(session: AsyncSession, raw: str | None, response: Response) -> TokenOut:
    if not raw:
        raise ApiError(401, "not_authenticated", "Требуется вход")
    row = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    ).scalar_one_or_none()
    if row is None or row.expires_at < utcnow():
        raise ApiError(401, "invalid_token", "Сессия истекла. Войдите снова.")
    if row.revoked_at is not None:
        # повторное использование ротированного токена: считаем компрометацией и закрываем все сессии
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == row.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        await session.commit()
        raise ApiError(401, "invalid_token", "Сессия недействительна. Войдите снова.")
    user = await session.get(User, row.user_id)
    if user is None:
        raise ApiError(401, "invalid_token", "Пользователь не найден")
    row.revoked_at = utcnow()
    return await issue_tokens(session, user, response)


async def logout(session: AsyncSession, raw: str | None, response: Response) -> None:
    if raw:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(raw), RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        await session.commit()
    response.delete_cookie(COOKIE, path=f"{get_settings().api_prefix}/auth")


async def change_password(session: AsyncSession, user: User, old: str, new: str) -> None:
    if not verify_password(user.password_hash, old):
        raise ApiError(403, "bad_credentials", "Текущий пароль указан неверно")
    user.password_hash = hash_password(new)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    await session.commit()
