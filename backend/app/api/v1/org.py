from fastapi import APIRouter

from app.core.deps import CurrentOrg
from app.schemas.auth import OrgOut

router = APIRouter(tags=["org"])


# GET /org -> 200 OK (404 if the token's org isn't one you belong to)
# Singular "/org", not "/orgs/{id}": you act inside one org at a time and it comes
# from your token, so there's no org id in the URL for anyone to tamper with.
@router.get("/org")
async def get_org(ctx: CurrentOrg) -> OrgOut:
    return OrgOut.model_validate(ctx.org)
