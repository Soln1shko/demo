from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.core.deps import Client, CurrentUser, Session
from app.core.rate_limit import RateLimit
from app.schemas.auth import (
    LoginIn,
    OperatorLoginIn,
    PasswordChangeIn,
    RegisterIn,
    ResetDemoIn,
    TokenOut,
    UserOut,
    UserPatch,
)
from app.services import auth as svc
from app.services import organizations as orgs

router = APIRouter(prefix="/auth", tags=["auth"])
limit_login = Depends(RateLimit(10, 60))


@router.post("/register", response_model=TokenOut, status_code=201, dependencies=[Depends(RateLimit(5, 60))])
async def register(body: RegisterIn, session: Session, response: Response):
    user = await svc.register(session, body)
    return await svc.issue_tokens(session, user, response)


@router.post("/login", response_model=TokenOut, dependencies=[limit_login])
async def login(body: LoginIn, session: Session, response: Response):
    user = await svc.authenticate(session, body.email, body.password)
    return await svc.issue_tokens(session, user, response)


@router.post("/operator/login", response_model=TokenOut, dependencies=[limit_login])
async def operator_login(body: OperatorLoginIn, session: Session, response: Response):
    user = await svc.authenticate_operator(session, body.operator_id, body.password)
    return await svc.issue_tokens(session, user, response)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    session: Session, response: Response, refresh_token: Annotated[str | None, Cookie()] = None
):
    return await svc.refresh(session, refresh_token, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(session: Session, response: Response, refresh_token: Annotated[str | None, Cookie()] = None):
    await svc.logout(session, refresh_token, response)
    response.status_code = 204


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser, session: Session):
    return await svc.user_out(session, user)


@router.patch("/me", response_model=UserOut)
async def patch_me(body: UserPatch, user: CurrentUser, session: Session):
    user.name = body.name.strip()
    await session.commit()
    return await svc.user_out(session, user)


@router.post("/me/password", status_code=204)
async def change_password(body: PasswordChangeIn, user: CurrentUser, session: Session):
    await svc.change_password(session, user, body.old_password, body.new_password)


@router.post("/me/reset-demo", response_model=UserOut)
async def reset_demo(_: ResetDemoIn, user: Client, session: Session):
    await orgs.reset_demo(session, user)
    return await svc.user_out(session, user)
