"""FastAPI dependencies for authentication and authorization.

Chain, each step building on the previous one:

    Authorization: Bearer <jwt>
      -> get_access_claims   verify signature/expiry               (401 if bad)
      -> get_current_user    load the user                         (401 if gone)
      -> get_current_org     check membership in the token's org   (404 if not a member)
      -> require_role(...)   check the role in that org            (403 if not allowed)

Routes declare what they need (`CurrentUser`, `CurrentOrg`, `Depends(require_role(...))`)
and receive it as an argument. A route that forgets to ask simply has no user/org to use.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import AccessClaims, decode_access_token
from app.db.session import get_db
from app.models import Organization, Role, User
from app.repositories.identity import OrganizationRepository, UserRepository
from app.repositories.memberships import MembershipRepository

DbSession = Annotated[AsyncSession, Depends(get_db)]

# auto_error=False: we raise our own RFC 7807 401 instead of FastAPI's default 403.
_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login")


async def get_access_claims(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AccessClaims:
    if creds is None:
        raise UnauthorizedError("Missing bearer token.")
    return decode_access_token(creds.credentials)


AccessToken = Annotated[AccessClaims, Depends(get_access_claims)]


async def get_current_user(claims: AccessToken, db: DbSession) -> User:
    user = await UserRepository(db).get(claims.sub)
    if user is None:
        raise UnauthorizedError("User no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass(frozen=True)
class OrgContext:
    """Who is calling, in which org, with which role. Services take `org_id` from here."""

    user: User
    org: Organization
    role: Role
    # Plain values copied at request start, so they stay readable even if the session
    # later expires the ORM objects (reading an expired attribute would hit the DB).
    org_id: uuid.UUID
    user_id: uuid.UUID


async def get_current_org(claims: AccessToken, user: CurrentUser, db: DbSession) -> OrgContext:
    # Membership is checked on every request (not trusted from the token), so removing
    # a member or changing their role takes effect immediately, not in 15 minutes.
    membership = await MembershipRepository(db, claims.org).get_for_user(user.id)
    org = await OrganizationRepository(db).get(claims.org) if membership else None
    if membership is None or org is None:
        raise NotFoundError("Organization not found.")
    return OrgContext(user=user, org=org, role=membership.role, org_id=org.id, user_id=user.id)


CurrentOrg = Annotated[OrgContext, Depends(get_current_org)]


def require_role(*allowed: Role) -> Callable[..., Awaitable[OrgContext]]:
    """Usage: `ctx: Annotated[OrgContext, Depends(require_role(Role.OWNER))]`.

    403 (not 404) here: the caller IS a member, so the org's existence isn't a secret;
    they just lack permission for this action.
    """

    async def _check(ctx: CurrentOrg) -> OrgContext:
        if ctx.role not in allowed:
            raise ForbiddenError(
                f"This action requires role: {', '.join(r.value for r in allowed)}."
            )
        return ctx

    return _check
