import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import tuple_

from app.models import Job, JobStatus
from app.repositories.base import TenantRepository


class JobRepository(TenantRepository[Job]):
    model = Job

    async def list_page(
        self,
        *,
        limit: int,
        status: JobStatus | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> Sequence[Job]:
        """Newest first. Fetches limit + 1 rows: the extra one only tells us whether a
        next page exists, without a separate COUNT query."""
        query = self._select().order_by(Job.created_at.desc(), Job.id.desc())
        if status is not None:
            query = query.where(Job.status == status)
        if after is not None:
            # Row-value comparison: "strictly older than the last item seen", with id as
            # the tie-breaker when two jobs share a timestamp.
            query = query.where(tuple_(Job.created_at, Job.id) < tuple_(*after))
        result = await self.session.execute(query.limit(limit + 1))
        return result.scalars().all()
