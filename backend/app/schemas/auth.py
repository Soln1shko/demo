from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.organization import OrganizationOut

EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    demo_consent: bool = False


class LoginIn(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(max_length=128)


class OperatorLoginIn(BaseModel):
    operator_id: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class UserPatch(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class PasswordChangeIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ResetDemoIn(BaseModel):
    confirm: Literal[True]


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    operator_id: str | None
    onboarding_complete: bool
    organizations: list[OrganizationOut]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
