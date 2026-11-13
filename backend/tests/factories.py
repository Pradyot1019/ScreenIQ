"""Small helpers for API tests.

Cookies are handled explicitly (read from Set-Cookie, sent as a Cookie header) rather
than via the client's cookie jar, so each test states exactly which refresh token it uses.
"""

from dataclasses import dataclass
from http.cookies import SimpleCookie

from httpx import AsyncClient, Response

from app.api.v1.auth import REFRESH_COOKIE

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
