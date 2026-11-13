"""Passwords, access tokens and refresh tokens. Pure functions, no database.

Two kinds of token, two different jobs:

- **Access token** (JWT, 15 min): sent on every API call as `Authorization: Bearer`.
  The server verifies its signature and expiry without touching the database, which
  is why it's fast, and also why it can't be revoked; we keep it short-lived instead.
- **Refresh token** (random string, 7 days): lives in an httpOnly cookie, is only
  sent to `/auth/*`, and is checked against the `refresh_tokens` table. That makes
  it revocable (logout) and rotatable (each use swaps it for a new one).
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import UnauthorizedError

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "screeniq"

# argon2id with the library's defaults (OWASP-recommended memory-hard settings).
_hasher = PasswordHasher()


# ---- Passwords ------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Returns an argon2id hash. The salt and parameters are embedded in the string."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# Used to make login take the same time whether or not the email exists, so response
# timing doesn't reveal which emails have accounts (user enumeration).
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


# ---- Access tokens (JWT) --------------------------------------------------------------


class AccessClaims(BaseModel):
    sub: uuid.UUID  # user id
    org: uuid.UUID  # active org id; membership is re-checked on every request
    type: Literal["access"]
    iat: int
    exp: int


def create_access_token(user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "type": "access",
        "iss": JWT_ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_min),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> AccessClaims:
    """Verifies signature, expiry, issuer and token type. Raises 401 on any failure."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITHM],  # pinned: never trust the token's own "alg" header
            issuer=JWT_ISSUER,
            options={"require": ["sub", "org", "exp", "iat", "iss"]},
        )
        return AccessClaims.model_validate(payload)
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedError("Access token expired.") from e
    except (jwt.InvalidTokenError, ValueError) as e:
        raise UnauthorizedError("Invalid access token.") from e


# ---- Refresh tokens (opaque) ----------------------------------------------------------


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the cookie, SHA-256 hash for the database)."""
    raw = secrets.token_urlsafe(32)  # 256 bits of randomness
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    # A fast hash is fine here (unlike passwords): the token is 256 random bits, so
    # there's nothing to brute-force, and a deterministic hash lets us look it up.
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=get_settings().jwt_refresh_ttl_days)
