"""TenantRepository: the one place tenant isolation is enforced (spec FR-06).

A repository is constructed *for one org*. Every query it builds starts from
`SELECT ... WHERE org_id = :org_id`, so a route or service can't forget the filter:
there is no method that reads across orgs.

Looking up another org's row by id therefore returns None, which the service turns
into a 404, not a 403. A 403 would confirm "this exists, you just can't see it",
which leaks information across tenants.
"""

import uuid
from collections.abc import Sequence
from typing import ClassVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mixins import TenantMixin


class TenantRepository[M: TenantMixin]:
    model: ClassVar[type[TenantMixin]]

    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    def _select(self) -> Select[M]:
        """Base query for every read. Subclasses add `.where(...)` to it, never replace it."""
        return select(self.model).where(self.model.org_id == self.org_id)  # type: ignore[return-value]

    async def get(self, id_: uuid.UUID) -> M | None:
        result = await self.session.execute(self._select().where(self.model.id == id_))
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[M]:
        result = await self.session.execute(self._select())
        return result.scalars().all()

    async def add(self, obj: M) -> M:
        # Stamp the org here, so callers can't create rows in another org by mistake.
        obj.org_id = self.org_id
        self.session.add(obj)
        await self.session.flush()
        return obj
