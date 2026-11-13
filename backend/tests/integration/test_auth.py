"""Phase 1 integration tests: auth endpoints against a real Postgres."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import REFRESH_COOKIE
from app.core.security import hash_refresh_token
from app.models import RefreshToken
from tests.factories import PASSWORD, call_refresh, refresh_cookie_from, session_from, signup

# ---- signup ---------------------------------------------------------------------------


async def test_signup_creates_user_org_and_owner_membership(api: AsyncClient) -> None:
    r = await api.post(
        "/api/v1/auth/signup",
        json={
            "email": "Prem@Example.com",
            "password": PASSWORD,
            "full_name": "  Prem  ",
            "org_name": "Acme Hiring",
        },
    )
    assert r.status_code == 201
    assert r.headers["Location"] == "/api/v1/me"
    assert r.headers["Cache-Control"] == "no-store"
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert "refresh" not in r.text  # refresh token only ever travels in the cookie

    cookie = refresh_cookie_from(r)[REFRESH_COOKIE]
    assert cookie["httponly"]
    assert cookie["path"] == "/api/v1/auth"
    assert cookie["samesite"].lower() == "lax"

    me = await api.get("/api/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    data = me.json()
    assert data["user"]["full_name"] == "Prem"  # whitespace stripped
    assert data["memberships"] == [
        {
            "org_id": data["active_org_id"],
            "org_name": "Acme Hiring",
            "org_slug": "acme-hiring",
            "role": "owner",
        }
    ]
    assert "password" not in me.text


async def test_signup_duplicate_email_is_409_case_insensitive(api: AsyncClient) -> None:
    await signup(api, "dup@example.com")
    r = await api.post(
        "/api/v1/auth/signup",
        json={"email": "DUP@example.com", "password": PASSWORD, "full_name": "X", "org_name": "Y"},
    )
    assert r.status_code == 409
    assert r.headers["content-type"] == "application/problem+json"


async def test_same_org_name_gets_a_unique_slug(api: AsyncClient) -> None:
    a = await signup(api, "a@example.com", org_name="Acme")
    b = await signup(api, "b@example.com", org_name="Acme")
    slug_a = (await api.get("/api/v1/org", headers=a.headers)).json()["slug"]
    slug_b = (await api.get("/api/v1/org", headers=b.headers)).json()["slug"]
    assert slug_a == "acme"
    assert slug_b.startswith("acme-") and slug_b != slug_a


async def test_signup_validation_errors_are_422(api: AsyncClient) -> None:
    bad = [
        {"email": "not-an-email", "password": PASSWORD, "full_name": "X", "org_name": "Y"},
        {"email": "x@example.com", "password": "short", "full_name": "X", "org_name": "Y"},
        {"email": "x@example.com", "password": PASSWORD, "full_name": "   ", "org_name": "Y"},
    ]
    for payload in bad:
        r = await api.post("/api/v1/auth/signup", json=payload)
        assert r.status_code == 422, payload
        assert r.json()["type"].endswith("validation-error")


# ---- login ----------------------------------------------------------------------------


async def test_login_success(api: AsyncClient) -> None:
    await signup(api, "login@example.com")
    r = await api.post(
        "/api/v1/auth/login", json={"email": "LOGIN@example.com", "password": PASSWORD}
    )
    assert r.status_code == 200
    s = session_from(r)
    assert (await api.get("/api/v1/me", headers=s.headers)).status_code == 200


async def test_login_failures_look_identical(api: AsyncClient) -> None:
    await signup(api, "real@example.com")
    wrong_pw = await api.post(
        "/api/v1/auth/login", json={"email": "real@example.com", "password": "wrong-password"}
    )
    no_user = await api.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "wrong-password"}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["detail"] == no_user.json()["detail"]  # no account enumeration
    assert wrong_pw.headers["WWW-Authenticate"] == "Bearer"


# ---- protected routes -----------------------------------------------------------------


async def test_me_without_token_is_401(api: AsyncClient) -> None:
    r = await api.get("/api/v1/me")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert r.headers["content-type"] == "application/problem+json"


async def test_me_with_garbage_token_is_401(api: AsyncClient) -> None:
    r = await api.get("/api/v1/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


# ---- refresh rotation -----------------------------------------------------------------


async def test_refresh_rotates_the_token(api: AsyncClient) -> None:
    s = await signup(api, "rot@example.com")
    r = await call_refresh(api, s.refresh_token)
    assert r.status_code == 200
    new = session_from(r)
    assert new.refresh_token != s.refresh_token
    assert (await api.get("/api/v1/me", headers=new.headers)).status_code == 200


async def test_reused_refresh_token_revokes_the_whole_family(api: AsyncClient) -> None:
    s = await signup(api, "reuse@example.com")
    second = session_from(await call_refresh(api, s.refresh_token))

    # An attacker replays the first (already used) token...
    assert (await call_refresh(api, s.refresh_token)).status_code == 401
    # ...so the legitimate newer token is revoked too; everyone must log in again.
    assert (await call_refresh(api, second.refresh_token)).status_code == 401


async def test_refresh_without_cookie_is_401(api: AsyncClient) -> None:
    api.cookies.clear()
    r = await api.post("/api/v1/auth/refresh")
    assert r.status_code == 401


async def test_expired_refresh_token_is_401(api: AsyncClient, db_session: AsyncSession) -> None:
    s = await signup(api, "exp@example.com")
    await db_session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(s.refresh_token))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    assert (await call_refresh(api, s.refresh_token)).status_code == 401


# ---- logout ---------------------------------------------------------------------------


async def test_logout_revokes_refresh_token_and_is_idempotent(api: AsyncClient) -> None:
    s = await signup(api, "bye@example.com")
    cookie = {"Cookie": f"{REFRESH_COOKIE}={s.refresh_token}"}

    r = await api.post("/api/v1/auth/logout", headers=cookie)
    assert r.status_code == 204
    assert 'screeniq_refresh=""' in r.headers["set-cookie"]  # browser deletes the cookie

    assert (await call_refresh(api, s.refresh_token)).status_code == 401
    assert (await api.post("/api/v1/auth/logout", headers=cookie)).status_code == 204
