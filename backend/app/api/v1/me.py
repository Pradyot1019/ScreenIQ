from fastapi import APIRouter

from app.core.deps import AccessToken, CurrentUser, DbSession
from app.repositories.identity import UserRepository
from app.schemas.auth import MembershipOut, MeOut, UserOut

router = APIRouter(tags=["me"])


# GET /me -> 200 OK
# "/me" is a common REST convention for "the resource that is the caller". It's a
# singular path because there's exactly one current user, so there's no id in the
# URL that someone could change to read another user's profile.
@router.get("/me")
async def get_me(user: CurrentUser, claims: AccessToken, db: DbSession) -> MeOut:
    rows = await UserRepository(db).memberships(user.id)
    return MeOut(
        user=UserOut.model_validate(user),
        active_org_id=claims.org,
        memberships=[
            MembershipOut(org_id=o.id, org_name=o.name, org_slug=o.slug, role=m.role)
            for m, o in rows
        ],
    )
