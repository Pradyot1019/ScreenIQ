"""Auth endpoints. Every route here is POST: each one changes server state
(creates a user, issues/rotates/revokes a refresh token). GET must be safe to repeat
and to prefetch, and must never put credentials in a URL, where they'd end up in logs.

The refresh token never appears in a response body. It travels only in an httpOnly
cookie, which page JavaScript can't read, so an XSS bug can't steal the long-lived token.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status

from app.core.config import get_settings
from app.core.deps import DbSession
from app.schemas.auth import LoginIn, SignupIn, TokenOut
from app.services.auth import AuthService, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "screeniq_refresh"
# The browser sends the cookie only to /api/v1/auth/*, never to /jobs etc.
REFRESH_COOKIE_PATH = "/api/v1/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _respond_with_tokens(response: Response, pair: TokenPair) -> TokenOut:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        pair.refresh_token,
        max_age=settings.jwt_refresh_ttl_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,  # invisible to document.cookie, so XSS can't read it
        secure=settings.cookie_secure,  # HTTPS-only outside local dev
        samesite="lax",  # not sent on cross-site POSTs, which blocks CSRF on /auth/*
    )
    # Tokens must never be cached by a browser or proxy (RFC 6749 §5.1).
    response.headers["Cache-Control"] = "no-store"
    return TokenOut(access_token=pair.access_token, expires_in=settings.jwt_access_ttl_min * 60)


# POST /auth/signup -> 201 Created + Location: /api/v1/me
# POST because it creates resources (user, org, membership). 201 (not 200) says
# "something new now exists", and Location points at where to read it.
@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupIn, response: Response, db: DbSession) -> TokenOut:
    pair = await AuthService(db).signup(
        email=body.email, password=body.password, full_name=body.full_name, org_name=body.org_name
    )
    response.headers["Location"] = "/api/v1/me"
    return _respond_with_tokens(response, pair)


# POST /auth/login -> 200 OK
# Not 201: a login session isn't a resource the client can GET at a URL afterwards.
# Wrong email OR wrong password -> the same 401, so attackers can't probe for accounts.
@router.post("/login")
async def login(body: LoginIn, response: Response, db: DbSession) -> TokenOut:
    pair = await AuthService(db).login(email=body.email, password=body.password)
    return _respond_with_tokens(response, pair)


# POST /auth/refresh -> 200 OK, new access token + new refresh cookie
# No body: the credential is the cookie. 401 if it's missing, expired, revoked or reused.
@router.post("/refresh")
async def refresh(response: Response, db: DbSession, token: RefreshCookie = None) -> TokenOut:
    pair = await AuthService(db).refresh(token)
    return _respond_with_tokens(response, pair)


# POST /auth/logout -> 204 No Content
# Nothing useful to return, so 204. Idempotent: logging out twice is still a 204.
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, db: DbSession, token: RefreshCookie = None) -> None:
    await AuthService(db).logout(token)
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
    )
