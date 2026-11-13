"""Applications and screenings (FR-30 to FR-34, FR-40 basics)."""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentOrg, DbSession, OrgContext, require_role
from app.models import Candidate, Role, Stage
from app.schemas.applications import (
    ApplicationDetail,
    ApplicationRow,
    CandidateBrief,
    ScreeningBrief,
    ScreeningOut,
    ScreeningQueued,
)
from app.services.screening import ScreeningService, SortKey
from app.workers.queue import Queue, get_queue

router = APIRouter(tags=["applications"])

Writer = Annotated[OrgContext, Depends(require_role(Role.OWNER, Role.RECRUITER))]
QueueDep = Annotated[Queue, Depends(get_queue)]


def _brief(c: Candidate) -> CandidateBrief:
    return CandidateBrief(
        id=c.id,
        full_name=c.full_name,
        email=c.email,
        total_experience_years=c.total_experience_years,
    )


# GET /jobs/{id}/applications?stage=&min_score=&knockout=&sort=-score -> 200
# Sub-collection of the job. Filters/sort are query params on the same resource.
# Not paginated: one job's applicants (hundreds at most) fit in one sorted response.
@router.get("/jobs/{job_id}/applications")
async def list_applications(
    job_id: uuid.UUID,
    ctx: CurrentOrg,
    db: DbSession,
    stage: Stage | None = None,
    min_score: Annotated[Decimal | None, Query(ge=0, le=100)] = None,
    knockout: bool | None = None,
    sort: SortKey = "-score",
) -> list[ApplicationRow]:
    rows = await ScreeningService(db, ctx).list_for_job(
        job_id, stage=stage, min_score=min_score, knockout=knockout, sort=sort
    )
    return [
        ApplicationRow(
            id=a.id,
            job_id=a.job_id,
            stage=a.stage,
            created_at=a.created_at,
            candidate=_brief(c),
            screening=ScreeningBrief.model_validate(s) if s else None,
        )
        for a, c, s in rows
    ]


# GET /applications/{id} -> 200 with the parsed profile and the latest screening
@router.get("/applications/{application_id}")
async def get_application(
    application_id: uuid.UUID, ctx: CurrentOrg, db: DbSession
) -> ApplicationDetail:
    app, candidate, screening = await ScreeningService(db, ctx).detail(application_id)
    return ApplicationDetail(
        id=app.id,
        job_id=app.job_id,
        stage=app.stage,
        created_at=app.created_at,
        candidate=_brief(candidate),
        profile=candidate.parsed,
        screening=ScreeningOut.model_validate(screening) if screening else None,
    )


# POST /applications/{id}/screenings -> 202 Accepted (re-screen; runs in the background)
# POST to the screenings sub-collection creates a new screening; old ones stay as history.
@router.post("/applications/{application_id}/screenings", status_code=status.HTTP_202_ACCEPTED)
async def rescreen(
    application_id: uuid.UUID, ctx: Writer, db: DbSession, queue: QueueDep, response: Response
) -> ScreeningBrief:
    screening = await ScreeningService(db, ctx).request(application_id)
    await queue.enqueue("screen_application", str(screening.id), job_id=f"screen:{screening.id}")
    response.headers["Location"] = f"/api/v1/applications/{application_id}"
    return ScreeningBrief.model_validate(screening)


# POST /jobs/{id}/screenings -> 202 {queued: n}: screen every not-yet-screened applicant
@router.post("/jobs/{job_id}/screenings", status_code=status.HTTP_202_ACCEPTED)
async def screen_pending(
    job_id: uuid.UUID, ctx: Writer, db: DbSession, queue: QueueDep
) -> ScreeningQueued:
    screenings = await ScreeningService(db, ctx).request_pending(job_id)
    for s in screenings:
        await queue.enqueue("screen_application", str(s.id), job_id=f"screen:{s.id}")
    return ScreeningQueued(queued=len(screenings))
