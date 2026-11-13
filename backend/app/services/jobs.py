"""Job business rules (FR-10 to FR-13).

Status machine (FR-13):   draft --publish--> open --close--> closed
- publish needs a saved rubric whose weights total 100 (you can't screen without one).
- Repeating a transition you're already in is a no-op success (safe to retry).
- Any other move is 409 Conflict: the request is valid, but the job's current state
  doesn't allow it.
"""

import secrets
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import OrgContext
from app.core.errors import ConflictError, NotFoundError
from app.core.pagination import decode_cursor, encode_cursor
from app.llm.provider import LLMProvider
from app.llm.runner import LLMRunner
from app.models import Job, JobStatus, RubricCriterion
from app.repositories.jobs import JobRepository
from app.schemas.jobs import CriterionIn, JobCreate, JobUpdate, RubricIn
from app.services.auth import slugify
from app.services.rubric import JD_PARSE_PROMPT, suggest_rubric


class JobService:
    def __init__(self, session: AsyncSession, ctx: OrgContext) -> None:
        self.session = session
        self.ctx = ctx
        self.jobs = JobRepository(session, ctx.org_id)

    async def get(self, job_id: uuid.UUID) -> Job:
        job = await self.jobs.get(job_id)
        if job is None:
            # Same answer whether the job doesn't exist or belongs to another org.
            raise NotFoundError("Job not found.")
        return job

    async def list_page(
        self, *, limit: int, status: JobStatus | None, cursor: str | None
    ) -> tuple[Sequence[Job], str | None]:
        after = decode_cursor(cursor) if cursor else None
        rows = await self.jobs.list_page(limit=limit, status=status, after=after)
        page = rows[:limit]
        has_more = len(rows) > limit
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if has_more else None
        return page, next_cursor

    async def create(self, data: JobCreate) -> Job:
        job = Job(
            **data.model_dump(),
            # Random suffix: titles repeat ("Backend Engineer"), and the slug is public
            # (/apply/{slug}), so it shouldn't be guessable either.
            slug=f"{slugify(data.title)[:60]}-{secrets.token_hex(4)}",
            created_by=self.ctx.user.id,
        )
        await self.jobs.add(job)
        await self.session.commit()
        return await self._reload(job.id)

    async def update(self, job_id: uuid.UUID, patch: JobUpdate) -> Job:
        job = await self.get(job_id)
        for field, value in patch.model_dump(exclude_unset=True).items():
            setattr(job, field, value)
        await self.session.commit()
        return job

    async def delete(self, job_id: uuid.UUID) -> None:
        job = await self.get(job_id)
        await self.session.delete(job)  # rubric criteria go with it (ON DELETE CASCADE)
        await self.session.commit()

    async def replace_rubric(self, job_id: uuid.UUID, rubric: RubricIn) -> Job:
        job = await self.get(job_id)
        if job.status == JobStatus.CLOSED:
            raise ConflictError("A closed job's rubric can't be changed.")
        # Assigning a new list replaces the whole rubric: the old rows are deleted
        # (delete-orphan) and the new ones inserted, in one transaction.
        job.criteria = [
            RubricCriterion(**c.model_dump(), position=i) for i, c in enumerate(rubric.criteria)
        ]
        await self.session.commit()
        return await self._reload(job.id)

    async def publish(self, job_id: uuid.UUID) -> Job:
        job = await self.get(job_id)
        if job.status == JobStatus.OPEN:
            return job
        if job.status == JobStatus.CLOSED:
            raise ConflictError("Closed jobs can't be reopened.")
        if not job.criteria or sum(c.weight for c in job.criteria) != 100:
            raise ConflictError("Save a rubric whose weights add up to 100 before publishing.")
        job.status = JobStatus.OPEN
        await self.session.commit()
        return job

    async def close(self, job_id: uuid.UUID) -> Job:
        job = await self.get(job_id)
        if job.status == JobStatus.CLOSED:
            return job
        if job.status == JobStatus.DRAFT:
            raise ConflictError("Only open jobs can be closed. Publish it first, or delete it.")
        job.status = JobStatus.CLOSED
        await self.session.commit()
        return job

    async def draft_rubric(
        self, job_id: uuid.UUID, provider: LLMProvider, jd_text: str | None
    ) -> tuple[list[CriterionIn], str]:
        job = await self.get(job_id)
        runner = LLMRunner(self.session, self.ctx.org_id, provider)
        criteria = await suggest_rubric(runner, jd_text or job.description)
        return criteria, JD_PARSE_PROMPT.id

    async def _reload(self, job_id: uuid.UUID) -> Job:
        """Re-read after insert so DB-generated values (created_at) and the fresh
        criteria list are populated."""
        self.session.expire_all()
        return await self.get(job_id)
