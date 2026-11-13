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
    CompareCandidate,
    CompareOut,
    HighlightOut,
    NoteIn,
    NoteOut,
    ResumeView,
    ScreeningBrief,
    ScreeningOut,
    ScreeningQueued,
    StageEventOut,
    StageIn,
)
from app.services.pipeline import InvalidCompareError, PipelineService
from app.services.screening import ScreeningService, SortKey
from app.storage.s3 import Storage, get_storage
from app.workers.queue import Queue, get_queue

SIGNED_URL_TTL = 300  # seconds

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
    history = await PipelineService(db, ctx).history(application_id)
    return ApplicationDetail(
        id=app.id,
        job_id=app.job_id,
        stage=app.stage,
        created_at=app.created_at,
        candidate=_brief(candidate),
        profile=candidate.parsed,
        screening=ScreeningOut.model_validate(screening) if screening else None,
        history=[
            StageEventOut(
                from_stage=e.from_stage,
                to_stage=e.to_stage,
                actor_name=u.full_name if u else None,
                created_at=e.created_at,
            )
            for e, u in history
        ],
    )


# PATCH /applications/{id} {"stage": "shortlisted"} -> 200
# PATCH: a partial update of the application (just its stage). Only people do this;
# moving to "rejected" is a human decision by design (FR-38). Each move is logged.
@router.patch("/applications/{application_id}")
async def move_stage(
    application_id: uuid.UUID, body: StageIn, ctx: Writer, db: DbSession
) -> ApplicationRow:
    app = await PipelineService(db, ctx).move(application_id, body.stage)
    _, candidate, screening = await ScreeningService(db, ctx).detail(app.id)
    return ApplicationRow(
        id=app.id,
        job_id=app.job_id,
        stage=app.stage,
        created_at=app.created_at,
        candidate=_brief(candidate),
        screening=ScreeningBrief.model_validate(screening) if screening else None,
    )


# GET /applications/{id}/notes -> 200 (oldest first)
@router.get("/applications/{application_id}/notes")
async def list_notes(application_id: uuid.UUID, ctx: CurrentOrg, db: DbSession) -> list[NoteOut]:
    rows = await PipelineService(db, ctx).notes(application_id)
    return [
        NoteOut(
            id=n.id, body=n.body, author_name=u.full_name if u else None, created_at=n.created_at
        )
        for n, u in rows
    ]


# POST /applications/{id}/notes -> 201. Any member, viewers included: hiring managers
# can't change stages or scores, but they can comment (spec Section 2).
@router.post("/applications/{application_id}/notes", status_code=status.HTTP_201_CREATED)
async def add_note(
    application_id: uuid.UUID, body: NoteIn, ctx: CurrentOrg, db: DbSession
) -> NoteOut:
    note = await PipelineService(db, ctx).add_note(application_id, body.body)
    return NoteOut(
        id=note.id, body=note.body, author_name=ctx.user.full_name, created_at=note.created_at
    )


# GET /applications/{id}/resume -> 200: text + evidence highlights + a 5-minute signed URL
# for the original file. A signed URL expires and works for one object only, so the
# bucket itself stays private (FR-21).
@router.get("/applications/{application_id}/resume")
async def get_resume(
    application_id: uuid.UUID,
    ctx: CurrentOrg,
    db: DbSession,
    storage: Annotated[Storage, Depends(get_storage)],
) -> ResumeView:
    resume, url, highlights = await PipelineService(db, ctx).resume(application_id, storage)
    return ResumeView(
        filename=resume.filename,
        mime_type=resume.mime_type,
        url=url,
        url_expires_in=SIGNED_URL_TTL,
        text=resume.raw_text or "",
        highlights=[
            HighlightOut(start=h.start, end=h.end, criterion=h.criterion) for h in highlights
        ],
    )


# GET /jobs/{id}/applications:compare?ids=a,b,c -> 200 (2-4 candidates side by side)
# A read-only "custom method" on the collection: GET because it changes nothing.
@router.get("/jobs/{job_id}/applications:compare")
async def compare(
    job_id: uuid.UUID,
    ctx: CurrentOrg,
    db: DbSession,
    ids: Annotated[str, Query(description="2-4 comma-separated application ids")],
) -> CompareOut:
    try:
        parsed = [uuid.UUID(x) for x in ids.split(",") if x.strip()]
    except ValueError as e:
        raise InvalidCompareError("ids must be comma-separated application ids.") from e
    columns = await PipelineService(db, ctx).compare(job_id, parsed)
    criteria: list[str] = []
    for col in columns:  # union of criteria, in rubric order
        for cs in col.screening.criterion_scores if col.screening else []:
            if cs.criterion_name not in criteria:
                criteria.append(cs.criterion_name)
    return CompareOut(
        criteria=criteria,
        candidates=[
            CompareCandidate(
                application_id=col.application.id,
                name=col.candidate.full_name,
                stage=col.application.stage,
                overall_score=col.screening.overall_score if col.screening else None,
                recommendation=col.screening.recommendation if col.screening else None,
                knockout_failed=col.screening.knockout_failed if col.screening else None,
                scores={cs.criterion_name: cs.score for cs in col.screening.criterion_scores}
                if col.screening
                else {},
                low_confidence=[
                    cs.criterion_name for cs in col.screening.criterion_scores if cs.low_confidence
                ]
                if col.screening
                else [],
            )
            for col in columns
        ],
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
