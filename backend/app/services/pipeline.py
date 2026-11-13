"""Recruiter workflow on applications (FR-41, FR-42, FR-45): stages, notes, history,
resume view with highlighted evidence, side-by-side comparison."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import OrgContext
from app.core.errors import AppError, NotFoundError
from app.models import (
    Application,
    Candidate,
    Note,
    Resume,
    Screening,
    Stage,
    StageEvent,
    User,
)
from app.pipeline.evidence import locate
from app.repositories.base import TenantRepository
from app.repositories.intake import ApplicationRepository, ResumeRepository
from app.repositories.jobs import JobRepository
from app.storage.s3 import Storage


class NoteRepository(TenantRepository[Note]):
    model = Note


class StageEventRepository(TenantRepository[StageEvent]):
    model = StageEvent


class InvalidCompareError(AppError):
    status, type_, title = 422, "invalid-compare", "Invalid comparison"


@dataclass(frozen=True)
class Highlight:
    start: int
    end: int
    criterion: str


@dataclass(frozen=True)
class CompareColumn:
    application: Application
    candidate: Candidate
    screening: Screening | None


class PipelineService:
    def __init__(self, session: AsyncSession, ctx: OrgContext) -> None:
        self.session = session
        self.ctx = ctx
        self.apps = ApplicationRepository(session, ctx.org_id)

    async def _application(self, application_id: uuid.UUID) -> Application:
        app = await self.apps.get(application_id)
        if app is None:
            raise NotFoundError("Application not found.")
        return app

    # ---- stages (FR-41) -----------------------------------------------------------------

    async def move(self, application_id: uuid.UUID, to: Stage) -> Application:
        """A human moves a candidate. Any stage is allowed, including rejected: that's
        exactly the decision the AI is never allowed to make (FR-38)."""
        app = await self._application(application_id)
        if app.stage != to:
            await StageEventRepository(self.session, self.ctx.org_id).add(
                StageEvent(
                    application_id=app.id,
                    from_stage=app.stage,
                    to_stage=to,
                    actor_id=self.ctx.user_id,
                )
            )
            app.stage = to
            await self.session.commit()
        return app

    async def history(self, application_id: uuid.UUID) -> Sequence[tuple[StageEvent, User | None]]:
        await self._application(application_id)
        result = await self.session.execute(
            select(StageEvent, User)
            .outerjoin(User, User.id == StageEvent.actor_id)
            .where(
                StageEvent.org_id == self.ctx.org_id,
                StageEvent.application_id == application_id,
            )
            .order_by(StageEvent.created_at, StageEvent.id)
        )
        return [(e, u) for e, u in result.all()]

    # ---- notes (FR-42) ------------------------------------------------------------------

    async def notes(self, application_id: uuid.UUID) -> Sequence[tuple[Note, User | None]]:
        await self._application(application_id)
        result = await self.session.execute(
            select(Note, User)
            .outerjoin(User, User.id == Note.author_id)
            .where(Note.org_id == self.ctx.org_id, Note.application_id == application_id)
            .order_by(Note.created_at, Note.id)
        )
        return [(n, u) for n, u in result.all()]

    async def add_note(self, application_id: uuid.UUID, body: str) -> Note:
        await self._application(application_id)
        note = await NoteRepository(self.session, self.ctx.org_id).add(
            Note(application_id=application_id, author_id=self.ctx.user_id, body=body)
        )
        await self.session.commit()
        await self.session.refresh(note)
        return note

    # ---- resume view (FR-21, FR-42) -----------------------------------------------------

    async def resume(
        self, application_id: uuid.UUID, storage: Storage
    ) -> tuple[Resume, str | None, list[Highlight]]:
        """The resume's text with every verified evidence quote located in it, plus a
        short-lived signed URL for the original file (never a public link)."""
        app = await self._application(application_id)
        resume = await ResumeRepository(self.session, self.ctx.org_id).get(app.resume_id)
        if resume is None:
            raise NotFoundError("Resume not found.")
        url = await storage.signed_url(resume.storage_key, 300) if resume.storage_key else None

        highlights: list[Highlight] = []
        screening = (
            await self.session.get(Screening, app.latest_screening_id)
            if app.latest_screening_id
            else None
        )
        if screening is not None and resume.raw_text:
            for cs in screening.criterion_scores:
                for quote in cs.evidence:
                    span = locate(quote, resume.raw_text)
                    if span is not None:
                        highlights.append(Highlight(span[0], span[1], cs.criterion_name))
        highlights.sort(key=lambda h: h.start)
        return resume, url, highlights

    # ---- compare (FR-45) ----------------------------------------------------------------

    async def compare(self, job_id: uuid.UUID, ids: list[uuid.UUID]) -> list[CompareColumn]:
        if not 2 <= len(set(ids)) <= 4:
            raise InvalidCompareError("Pick between 2 and 4 different candidates to compare.")
        if await JobRepository(self.session, self.ctx.org_id).get(job_id) is None:
            raise NotFoundError("Job not found.")
        columns: list[CompareColumn] = []
        for application_id in dict.fromkeys(ids):  # keep the order the user picked
            app = await self.apps.get(application_id)
            if app is None or app.job_id != job_id:
                raise NotFoundError("Application not found.")
            candidate = await self.session.get(Candidate, app.candidate_id)
            assert candidate is not None
            screening = (
                await self.session.get(Screening, app.latest_screening_id)
                if app.latest_screening_id
                else None
            )
            columns.append(CompareColumn(app, candidate, screening))
        return columns
