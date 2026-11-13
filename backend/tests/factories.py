"""Small helpers for API tests.

Cookies are handled explicitly (read from Set-Cookie, sent as a Cookie header) rather
than via the client's cookie jar, so each test states exactly which refresh token it uses.
"""

import uuid
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import REFRESH_COOKIE
from app.models import Role

PASSWORD = "correct-horse-battery"


@dataclass
class Session:
    access_token: str
    refresh_token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


def refresh_cookie_from(r: Response) -> SimpleCookie:
    jar: SimpleCookie = SimpleCookie()
    for header in r.headers.get_list("set-cookie"):
        jar.load(header)
    return jar


def session_from(r: Response) -> Session:
    return Session(r.json()["access_token"], refresh_cookie_from(r)[REFRESH_COOKIE].value)


async def signup(
    api: AsyncClient, email: str, org_name: str = "Acme Corp", password: str = PASSWORD
) -> Session:
    r = await api.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "full_name": "Test User", "org_name": org_name},
    )
    assert r.status_code == 201, r.text
    api.cookies.clear()
    return session_from(r)


async def call_refresh(api: AsyncClient, refresh_token: str) -> Response:
    api.cookies.clear()
    return await api.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={refresh_token}"}
    )


# ---- Phase 2 helpers ------------------------------------------------------------------

JD_TEXT = (
    "We are hiring a backend engineer with 3+ years of Python, FastAPI and PostgreSQL "
    "experience to build REST APIs for our logistics platform."
)


def valid_rubric() -> dict[str, object]:
    return {
        "criteria": [
            {"name": "Python", "type": "skill", "weight": 50, "is_knockout": True},
            {"name": "PostgreSQL", "type": "skill", "weight": 30},
            {"name": "3+ years backend", "type": "experience", "weight": 20},
        ]
    }


async def create_job(
    api: AsyncClient, headers: dict[str, str], **overrides: object
) -> dict[str, Any]:
    body = {"title": "Backend Engineer", "description": JD_TEXT, **overrides}
    r = await api.post("/api/v1/jobs", json=body, headers=headers)
    assert r.status_code == 201, r.text
    result: dict[str, Any] = r.json()
    return result


async def add_member(db: AsyncSession, org_id: uuid.UUID, role: Role) -> dict[str, str]:
    """Create a user with `role` in an existing org; return auth headers for them.
    (Invites arrive in a later phase, so tests insert the membership directly.)"""
    from app.core.security import create_access_token, hash_password
    from app.models import Membership, User

    user = User(
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password(PASSWORD),
        full_name=f"Test {role.value}",
    )
    db.add(user)
    await db.flush()
    db.add(Membership(user_id=user.id, org_id=org_id, role=role))
    await db.flush()
    return {"Authorization": f"Bearer {create_access_token(user.id, org_id)}"}
