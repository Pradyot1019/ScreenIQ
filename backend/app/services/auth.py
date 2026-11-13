"""Auth business logic: signup, login, refresh-token rotation, logout.

Services raise domain errors (ConflictError, UnauthorizedError); they never touch
HTTP, cookies or status codes. The router translates.
"""

import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.models import Membership, Organization, RefreshToken, Role, User
from app.repositories.identity import (
    OrganizationRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.repositories.memberships import MembershipRepository

logger = logging.getLogger(__name__)

INVALID_LOGIN = "Invalid email or password."  # same message for both cases: no enumeration
INVALID_REFRESH = "Session expired. Please log in again."


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str  # raw value, goes into the cookie; only its hash is stored
    refresh_expires_at: datetime


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]
    return slug or "org"


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.orgs = OrganizationRepository(session)
        self.tokens = RefreshTokenRepository(session)

    # ---- signup (FR-01, FR-04) ----------------------------------------------------------

    async def signup(
        self, *, email: str, password: str, full_name: str, org_name: str
    ) -> TokenPair:
        """Creates user + org + owner membership in ONE transaction, then logs them in."""
        if await self.users.get_by_email(email):
            raise ConflictError("An account with this email already exists.")

        org = await self.orgs.add(
            Organization(name=org_name, slug=await self._unique_slug(org_name))
        )
        try:
            user = await self.users.add(
                User(email=email, password_hash=hash_password(password), full_name=full_name)
            )
        except IntegrityError as e:
            # Two signups with the same email at the same instant: both pass the check
            # above, but the UNIQUE constraint lets only one insert win.
            await self.session.rollback()
            raise ConflictError("An account with this email already exists.") from e

        await MembershipRepository(self.session, org.id).add(
            Membership(user_id=user.id, role=Role.OWNER)
        )
        pair = await self._issue_tokens(user.id, org.id)
        await self.session.commit()
        logger.info("signup", extra={"extra_fields": {"user_id": str(user.id)}})  # no email: PII
        return pair

    async def _unique_slug(self, name: str) -> str:
        base = slugify(name)
        slug = base
        while await self.orgs.slug_exists(slug):
            slug = f"{base}-{secrets.token_hex(3)}"
        return slug

    # ---- login (FR-02) ------------------------------------------------------------------

    async def login(self, *, email: str, password: str) -> TokenPair:
        user = await self.users.get_by_email(email)
        if user is None:
            verify_password(password, DUMMY_PASSWORD_HASH)  # equalise timing
            raise UnauthorizedError(INVALID_LOGIN)
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError(INVALID_LOGIN)

        memberships = await self.users.memberships(user.id)
        if not memberships:
            raise UnauthorizedError("This account doesn't belong to any organization.")
        default_org_id = memberships[0][1].id

        pair = await self._issue_tokens(user.id, default_org_id)
        await self.session.commit()
        logger.info("login", extra={"extra_fields": {"user_id": str(user.id)}})
        return pair

    # ---- refresh with rotation (FR-02) --------------------------------------------------

    async def refresh(self, raw_token: str | None) -> TokenPair:
        """Swaps a valid refresh token for a new pair. The old token dies immediately.

        Reuse detection: a refresh token is single-use, so seeing a *revoked* one again
        means it was copied (stolen) and someone already used it. We can't tell the
        thief from the real user, so we revoke every session for that user and force
        a fresh login.
        """
        if not raw_token:
            raise UnauthorizedError(INVALID_REFRESH)
        now = datetime.now(UTC)
        row = await self.tokens.get_by_hash_for_update(hash_refresh_token(raw_token))
        if row is None:
            raise UnauthorizedError(INVALID_REFRESH)

        if row.revoked_at is not None:
            await self.tokens.revoke_all_for_user(row.user_id, now)
            await self.session.commit()
            logger.warning(
                "refresh_token_reuse_detected",
                extra={"extra_fields": {"user_id": str(row.user_id)}},
            )
            raise UnauthorizedError(INVALID_REFRESH)

        if row.expires_at <= now:
            raise UnauthorizedError(INVALID_REFRESH)

        # Still a member of that org? (They may have been removed since logging in.)
        if await MembershipRepository(self.session, row.org_id).get_for_user(row.user_id) is None:
            row.revoked_at = now
            await self.session.commit()
            raise UnauthorizedError(INVALID_REFRESH)

        row.revoked_at = now
        pair = await self._issue_tokens(row.user_id, row.org_id)
        await self.session.commit()
        return pair

    # ---- logout -------------------------------------------------------------------------

    async def logout(self, raw_token: str | None) -> None:
        """Revokes this session's refresh token. Idempotent: unknown tokens are ignored."""
        if not raw_token:
            return
        row = await self.tokens.get_by_hash_for_update(hash_refresh_token(raw_token))
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            await self.session.commit()

    # ---- helpers ------------------------------------------------------------------------

    async def _issue_tokens(self, user_id: uuid.UUID, org_id: uuid.UUID) -> TokenPair:
        raw, token_hash = new_refresh_token()
        expires_at = refresh_token_expiry()
        await self.tokens.add(
            RefreshToken(
                user_id=user_id, org_id=org_id, token_hash=token_hash, expires_at=expires_at
            )
        )
        return TokenPair(create_access_token(user_id, org_id), raw, expires_at)
