"""Request/response bodies for auth, /me and /org.

Request models validate input at the edge (bad input -> 422 before any code runs).
Response models whitelist output: `password_hash` can't leak because it isn't declared.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.models import Plan, Role

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# No strip/normalisation on passwords: " secret" and "secret" are different passwords.
# 128 max stops someone sending a 10 MB "password" to make argon2 burn CPU.
NewPassword = Annotated[str, Field(min_length=8, max_length=128)]


class SignupIn(BaseModel):
    email: EmailStr
    password: NewPassword
    full_name: Name
    org_name: Name


class LoginIn(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - the scheme name, not a secret
    expires_in: int = Field(description="Access token lifetime in seconds")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    email_verified: bool


class MembershipOut(BaseModel):
    org_id: uuid.UUID
    org_name: str
    org_slug: str
    role: Role


class MeOut(BaseModel):
    user: UserOut
    active_org_id: uuid.UUID
    memberships: list[MembershipOut]


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    plan: Plan
    blind_mode_default: bool
    created_at: datetime
