"""AI screening (FR-30 to FR-34, FR-36, FR-38).

API side (`ScreeningService`): queue screenings, list/read results.
Worker side (`ScreeningRunner`): one LLM call per application, then evidence checks and
deterministic scoring. The AI only scores; it never changes a candidate's stage to
rejected (FR-38). The one stage move it makes is applied -> screened.
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import OrgContext
from app.core.errors import (
    BadGatewayError,
    ConflictError,
    GatewayTimeoutError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.llm.prompts import load_prompt
from app.llm.provider import LLMProvider
from app.llm.runner import LLMRunner
from app.llm.schemas import make_screening_model
from app.models import (
    Application,
    Candidate,
    CriterionScore,
    Job,
    LLMPurpose,
    RubricCriterion,
    Screening,
    ScreeningStatus,
    Stage,
    StageEvent,
)
from app.pipeline.score import (
    CriterionInput,
    knockout_failed,
    overall_score,
    recommend,
    verify_criterion,
)
from app.repositories.base import TenantRepository
from app.repositories.intake import ApplicationRepository, ResumeRepository
from app.repositories.jobs import JobRepository
from app.services.intake import TransientParseError

SCREEN_PROMPT = load_prompt("screen", 1)
ACTIVE = (ScreeningStatus.QUEUED, ScreeningStatus.RUNNING)


class ScreeningRepository(TenantRepository[Screening]):
    model = Screening


def rubric_ready(job: Job) -> bool:
    return bool(job.criteria) and sum(c.weight for c in job.criteria) == 100


async def queue_screening(
    session: AsyncSession, org_id: uuid.UUID, application: Application
) -> Screening | None:
    """Create a queued screening unless one is already queued/running (then reuse it).
    Returns None if the job has no usable rubric yet. The caller commits and enqueues."""
    if application.latest_screening_id:
        latest = await ScreeningRepository(session, org_id).get(application.latest_screening_id)
        if latest is not None and latest.status in ACTIVE:
            return latest
    job = await JobRepository(session, org_id).get(application.job_id)
    if job is None or not rubric_ready(job):
        return None
    screening = await ScreeningRepository(session, org_id).add(
        Screening(application_id=application.id)
    )
    application.latest_screening_id = screening.id
    return screening


# ---- API side ---------------------------------------------------------------------------

SortKey = Literal["-score", "score", "-created_at"]


class ScreeningService:
    def __init__(self, session: AsyncSession, ctx: OrgContext) -> None:
        self.session = session
        self.ctx = ctx
        self.apps = ApplicationRepository(session, ctx.org_id)

    async def _application(self, application_id: uuid.UUID) -> Application:
        app = await self.apps.get(application_id)
        if app is None:
            raise NotFoundError("Application not found.")
        return app

    async def _job(self, job_id: uuid.UUID) -> Job:
        job = await JobRepository(self.session, self.ctx.org_id).get(job_id)
        if job is None:
            raise NotFoundError("Job not found.")
        return job

    async def request(self, application_id: uuid.UUID) -> Screening:
        app = await self._application(application_id)
        screening = await queue_screening(self.session, self.ctx.org_id, app)
        if screening is None:
            raise ConflictError("Save a rubric whose weights add up to 100 before screening.")
        await self.session.commit()
        return screening

    async def request_pending(self, job_id: uuid.UUID) -> list[Screening]:
        """Queue every application of the job that has no screening, or whose last one failed."""
        job = await self._job(job_id)
        if not rubric_ready(job):
            raise ConflictError("Save a rubric whose weights add up to 100 before screening.")
        rows = await self.list_for_job(job_id)
        queued: list[Screening] = []
        for app, _, latest in rows:
            if latest is None or latest.status == ScreeningStatus.FAILED:
                s = await queue_screening(self.session, self.ctx.org_id, app)
                if s is not None:
                    queued.append(s)
        await self.session.commit()
        return queued

    async def list_for_job(
        self,
        job_id: uuid.UUID,
        *,
        stage: Stage | None = None,
        min_score: Decimal | None = None,
        knockout: bool | None = None,
        sort: SortKey = "-score",
        limit: int = 500,
    ) -> Sequence[tuple[Application, Candidate, Screening | None]]:
        await self._job(job_id)  # 404 for another org's job
        query: Select[Application, Candidate, Screening] = (
            select(Application, Candidate, Screening)
            .join(Candidate, Candidate.id == Application.candidate_id)
            .outerjoin(Screening, Screening.id == Application.latest_screening_id)
            .where(Application.org_id == self.ctx.org_id, Application.job_id == job_id)
        )
        if stage is not None:
            query = query.where(Application.stage == stage)
        if min_score is not None:
            query = query.where(Screening.overall_score >= min_score)
        if knockout is not None:
            query = query.where(Screening.knockout_failed.is_(knockout))
        if sort == "-score":  # best first; not-yet-screened at the bottom
            query = query.order_by(
                Screening.overall_score.desc().nulls_last(), Application.created_at
            )
        elif sort == "score":
            query = query.order_by(
                Screening.overall_score.asc().nulls_last(), Application.created_at
            )
        else:
            query = query.order_by(Application.created_at.desc(), Application.id)
        result = await self.session.execute(query.limit(limit))
        return [(a, c, s) for a, c, s in result.all()]

    async def detail(
        self, application_id: uuid.UUID
    ) -> tuple[Application, Candidate, Screening | None]:
        self.session.expire_all()  # fresh status while the worker updates it
        app = await self._application(application_id)
        candidate = await self.session.get(Candidate, app.candidate_id)
        assert candidate is not None and candidate.org_id == self.ctx.org_id
        screening = (
            await ScreeningRepository(self.session, self.ctx.org_id).get(app.latest_screening_id)
            if app.latest_screening_id
            else None
        )
        return app, candidate, screening


# ---- Worker side ------------------------------------------------------------------------


def rubric_prompt(criteria: list[RubricCriterion]) -> tuple[str, dict[str, RubricCriterion]]:
    """Short keys (c1, c2...) instead of UUIDs: fewer tokens, nothing for the model to mistype."""
    by_key = {f"c{i + 1}": c for i, c in enumerate(criteria)}
    lines = [
        f"{key}: {c.name} [weight {c.weight}{', KNOCKOUT' if c.is_knockout else ''}]"
        f"{': ' + c.description if c.description else ''}"
        for key, c in by_key.items()
    ]
    return "\n".join(lines), by_key


class ScreeningRunner:
    def __init__(self, session: AsyncSession, provider: LLMProvider | None = None) -> None:
        self.session = session
        self.provider = provider

    async def run(self, screening_id: uuid.UUID) -> None:
        screening = await self.session.get(Screening, screening_id)
        if screening is None or screening.status not in ACTIVE:
            return  # already finished: duplicate delivery is a no-op
        org_id = screening.org_id
        app = await ApplicationRepository(self.session, org_id).get(screening.application_id)
        job = await JobRepository(self.session, org_id).get(app.job_id) if app else None
        resume = await ResumeRepository(self.session, org_id).get(app.resume_id) if app else None
        if app is None or job is None or resume is None or not resume.raw_text:
            await self.fail(screening_id, "The application or its resume no longer exists.")
            return
        if not rubric_ready(job):
            await self.fail(
                screening_id, "The job's rubric isn't complete (weights must total 100)."
            )
            return
        if self.provider is None:
            raise ServiceUnavailableError("No LLM provider configured.")

        screening.status = ScreeningStatus.RUNNING
        await self.session.commit()

        rubric_text, by_key = rubric_prompt(list(job.criteria))
        try:
            result = await LLMRunner(self.session, org_id, self.provider).run(
                purpose=LLMPurpose.SCREEN,
                prompt=SCREEN_PROMPT,
                variables={"rubric": rubric_text, "resume_text": resume.raw_text},
                output=make_screening_model(list(by_key)),
            )
        except BadGatewayError:
            await self.fail(screening_id, "The AI returned an invalid result. Try re-screening.")
            return
        except (ServiceUnavailableError, GatewayTimeoutError) as e:
            screening.status = ScreeningStatus.QUEUED
            await self.session.commit()
            raise TransientParseError(type(e).__name__) from e

        verdicts = {v.key: v for v in result.criteria}
        checked = [
            verify_criterion(
                CriterionInput(
                    name=c.name,
                    weight=c.weight,
                    is_knockout=c.is_knockout,
                    score=verdicts[key].score,
                    reasoning=verdicts[key].reasoning,
                    evidence=verdicts[key].evidence,
                ),
                resume.raw_text,
            )
            for key, c in by_key.items()
        ]
        score = overall_score(checked)
        knocked_out = knockout_failed(checked)

        screening.criterion_scores = [
            CriterionScore(
                criterion_id=c.id,
                position=i,
                criterion_name=r.name,
                weight=r.weight,
                is_knockout=r.is_knockout,
                score=r.score,
                reasoning=r.reasoning,
                evidence=r.evidence,
                rejected_evidence=r.rejected_evidence,
                low_confidence=r.low_confidence,
            )
            for i, (c, r) in enumerate(zip(by_key.values(), checked, strict=True))
        ]
        screening.overall_score = score
        screening.knockout_failed = knocked_out
        screening.recommendation = recommend(score, knocked_out)
        screening.strengths = result.strengths
        screening.gaps = result.gaps
        screening.summary = result.summary
        screening.model = self.provider.model
        screening.prompt_version = SCREEN_PROMPT.id
        screening.status = ScreeningStatus.DONE
        screening.error = None
        app.latest_screening_id = screening.id
        if app.stage == Stage.APPLIED:
            app.stage = Stage.SCREENED  # the only stage change the AI ever makes
            self.session.add(  # actor_id None = the system, shown as "AI screening"
                StageEvent(
                    org_id=org_id,
                    application_id=app.id,
                    from_stage=Stage.APPLIED,
                    to_stage=Stage.SCREENED,
                )
            )
        await self.session.commit()

    async def fail(self, screening_id: uuid.UUID, reason: str) -> None:
        screening = await self.session.get(Screening, screening_id)
        if screening is None or screening.status not in ACTIVE:
            return
        screening.status = ScreeningStatus.FAILED
        screening.error = reason
        await self.session.commit()
