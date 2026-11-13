import uuid

from app.models import Membership
from app.repositories.base import TenantRepository


class MembershipRepository(TenantRepository[Membership]):
    model = Membership

    async def get_for_user(self, user_id: uuid.UUID) -> Membership | None:
        """The user's membership in *this* org, or None if they don't belong to it."""
        result = await self.session.execute(self._select().where(Membership.user_id == user_id))
        return result.scalar_one_or_none()
