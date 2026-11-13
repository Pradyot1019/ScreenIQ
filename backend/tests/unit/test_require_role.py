"""require_role(...) unit tests. The org lookup is stubbed, so no DB is needed."""

import uuid
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.deps import OrgContext, get_current_org, require_role
from app.core.errors import register_exception_handlers
from app.models import Organization, Role, User


def _app(role: Role) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.delete("/owner-only")
    async def owner_only(
        ctx: Annotated[OrgContext, Depends(require_role(Role.OWNER))],
    ) -> dict[str, str]:
        return {"ok": ctx.role.value}

    @app.post("/writers")
    async def writers(
        ctx: Annotated[OrgContext, Depends(require_role(Role.OWNER, Role.RECRUITER))],
    ) -> dict[str, str]:
        return {"ok": ctx.role.value}

    async def _fake_org() -> OrgContext:
        user = User(id=uuid.uuid4(), email="x@example.com", full_name="X", password_hash="-")
        org = Organization(id=uuid.uuid4(), name="Org", slug="org")
        return OrgContext(user=user, org=org, role=role, org_id=org.id, user_id=user.id)

    app.dependency_overrides[get_current_org] = _fake_org
    return app


@pytest.mark.parametrize(
    ("role", "owner_only", "writers"),
    [(Role.OWNER, 200, 200), (Role.RECRUITER, 403, 200), (Role.VIEWER, 403, 403)],
)
async def test_require_role(role: Role, owner_only: int, writers: int) -> None:
    async with AsyncClient(transport=ASGITransport(app=_app(role)), base_url="http://t") as c:
        assert (await c.delete("/owner-only")).status_code == owner_only
        assert (await c.post("/writers")).status_code == writers
