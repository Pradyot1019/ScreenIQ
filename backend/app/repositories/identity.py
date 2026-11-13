"""Repositories for the identity layer: users, organizations, refresh tokens.

These are deliberately NOT tenant-scoped. They sit *above* tenancy: you need them
to work out which org a request belongs to in the first place (login, signup,
refresh). Every query here is keyed by a user id, an email, a slug or a token hash,
never "list everything".
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Membership, Organization, RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        # email is CITEXT, so this comparison is case-insensitive in Postgres.
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def memberships(self, user_id: uuid.UUID) -> Sequence[tuple[Membership, Organization]]:
        """All orgs this user belongs to, oldest first (the first is the default org)."""
        result = await self.session.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.org_id)
            .where(Membership.user_id == user_id)
            .order_by(Membership.created_at, Membership.id)
        )
        return [(m, o) for m, o in result.all()]


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, org_id: uuid.UUID) -> Organization | None:
        return await self.session.get(Organization, org_id)

    async def slug_exists(self, slug: str) -> bool:
        result = await self.session.execute(
            select(Organization.id).where(Organization.slug == slug)
        )
        return result.first() is not None

    async def add(self, org: Organization) -> Organization:
        self.session.add(org)
        await self.session.flush()
        return org


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None:
        # FOR UPDATE locks the row until commit. If two requests refresh with the same
        # token at the same moment, the second waits and then sees it already revoked,
        # instead of both succeeding and minting two valid tokens.
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        )
        return result.scalar_one_or_none()

    async def revoke_all_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
