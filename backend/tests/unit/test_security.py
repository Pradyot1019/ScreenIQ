"""Phase 1 unit tests for passwords, JWTs and refresh tokens. No DB required."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.core.security import (
    JWT_ALGORITHM,
    JWT_ISSUER,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    h = hash_password("correct horse battery staple")
    assert h.startswith("$argon2id$")
    assert "correct horse" not in h
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong password", h)


def test_same_password_hashes_differently() -> None:
    # Random salt per hash: identical passwords don't produce identical hashes.
    assert hash_password("same") != hash_password("same")


def test_verify_password_rejects_garbage_hash() -> None:
    assert not verify_password("anything", "not-a-real-hash")


def test_access_token_roundtrip() -> None:
    user_id, org_id = uuid.uuid4(), uuid.uuid4()
    claims = decode_access_token(create_access_token(user_id, org_id))
    assert claims.sub == user_id
    assert claims.org == org_id
    assert claims.exp - claims.iat == get_settings().jwt_access_ttl_min * 60


def _forge(payload: dict[str, object], secret: str | None = None) -> str:
    return jwt.encode(payload, secret or get_settings().jwt_secret, algorithm=JWT_ALGORITHM)


def _payload(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    base: dict[str, object] = {
        "sub": str(uuid.uuid4()),
        "org": str(uuid.uuid4()),
        "type": "access",
        "iss": JWT_ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    base.update(overrides)
    return base


def test_expired_token_rejected() -> None:
    past = datetime.now(UTC) - timedelta(minutes=1)
    with pytest.raises(UnauthorizedError, match="expired"):
        decode_access_token(_forge(_payload(exp=past)))


def test_token_signed_with_other_secret_rejected() -> None:
    with pytest.raises(UnauthorizedError):
        decode_access_token(_forge(_payload(), secret="attacker-secret-attacker-secret-xx"))


def test_tampered_token_rejected() -> None:
    token = create_access_token(uuid.uuid4(), uuid.uuid4())
    header, payload, sig = token.split(".")
    tampered = f"{header}.{payload[:-2]}AA.{sig}"
    with pytest.raises(UnauthorizedError):
        decode_access_token(tampered)


def test_alg_none_token_rejected() -> None:
    # Classic JWT attack: an unsigned token claiming alg "none".
    unsigned = jwt.encode(_payload(), key="", algorithm="none")
    with pytest.raises(UnauthorizedError):
        decode_access_token(unsigned)


@pytest.mark.parametrize(
    "overrides",
    [{"type": "refresh"}, {"iss": "someone-else"}, {"org": "not-a-uuid"}],
    ids=["wrong-type", "wrong-issuer", "bad-org"],
)
def test_wrong_claims_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(UnauthorizedError):
        decode_access_token(_forge(_payload(**overrides)))


def test_missing_org_claim_rejected() -> None:
    payload = _payload()
    del payload["org"]
    with pytest.raises(UnauthorizedError):
        decode_access_token(_forge(payload))


def test_refresh_token_is_random_and_hashed() -> None:
    raw1, hash1 = new_refresh_token()
    raw2, _ = new_refresh_token()
    assert raw1 != raw2
    assert len(raw1) >= 43  # 32 bytes, base64url
    assert hash1 == hash_refresh_token(raw1)  # deterministic, so we can look it up
    assert raw1 not in hash1


def test_default_jwt_secret_refused_in_production() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret="change-me-dev-only-not-a-real-secret-000")
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret="too-short")
    Settings(app_env="production", jwt_secret="x" * 32)  # a long random secret is fine
