"""Jobs and rubric endpoints (FR-10 to FR-13).

Who can do what: every member can read; owners and recruiters can write; viewers
(hiring managers) get 403 on writes. Another org's job is always 404.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentOrg, DbSession, OrgContext, require_role
from app.llm.provider import LLMProvider, get_llm_provider
from app.models import JobStatus, Role
from app.schemas.jobs import (
    JobCreate,
    JobOut,
    JobPage,
    JobSummaryOut,
    JobUpdate,
    RubricDraftIn,
    RubricDraftOut,
    RubricIn,
)
from app.services.jobs import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

Writer = Annotated[OrgContext, Depends(require_role(Role.OWNER, Role.RECRUITER))]
Provider = Annotated[LLMProvider, Depends(get_llm_provider)]


# GET /jobs?status=open&limit=20&cursor=... -> 200 {items, next_cursor}
# Plural noun for the collection. Filters are query params because they narrow the same
# resource rather than naming a different one. Paginated so it stays fast at 10k jobs.
@router.get("")
async def list_jobs(
    ctx: CurrentOrg,
    db: DbSession,
    status_: Annotated[JobStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> JobPage:
    jobs, next_cursor = await JobService(db, ctx).list_page(
        limit=limit, status=status_, cursor=cursor
    )
    return JobPage(items=[JobSummaryOut.from_job(j) for j in jobs], next_cursor=next_cursor)


# POST /jobs -> 201 Created + Location: /api/v1/jobs/{id}
# POST to the collection creates a member whose id the server picks. 201 + Location
# tells the client where the new job lives. New jobs always start as "draft".
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_job(body: JobCreate, ctx: Writer, db: DbSession, response: Response) -> JobOut:
    job = await JobService(db, ctx).create(body)
    response.headers["Location"] = f"/api/v1/jobs/{job.id}"
    return JobOut.model_validate(job)


# GET /jobs/{id} -> 200 (404 if missing OR in another org: we don't reveal which)
@router.get("/{job_id}")
async def get_job(job_id: uuid.UUID, ctx: CurrentOrg, db: DbSession) -> JobOut:
    return JobOut.model_validate(await JobService(db, ctx).get(job_id))


# PATCH /jobs/{id} -> 200 with the updated job
# PATCH = partial update: send only what changed. (PUT would mean "replace the whole
# job", forcing the client to resend the full description just to fix a typo.)
@router.patch("/{job_id}")
async def update_job(job_id: uuid.UUID, body: JobUpdate, ctx: Writer, db: DbSession) -> JobOut:
    return JobOut.model_validate(await JobService(db, ctx).update(job_id, body))


# DELETE /jobs/{id} -> 204 No Content (deleted; nothing left to return)
@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: uuid.UUID, ctx: Writer, db: DbSession) -> None:
    await JobService(db, ctx).delete(job_id)


# POST /jobs/{id}/rubric:generate -> 200 {criteria, prompt_version}  (nothing saved)
# A "custom method" (Google API style `resource:verb`): an action that doesn't fit
# create/read/update/delete. POST because it isn't safe or idempotent: every call costs
# tokens and may return a different draft. It returns a suggestion and saves nothing;
# the recruiter edits it and saves with PUT /rubric, so a human approves every rubric.
@router.post("/{job_id}/rubric:generate")
async def generate_rubric(
    job_id: uuid.UUID,
    ctx: Writer,
    db: DbSession,
    provider: Provider,
    body: RubricDraftIn | None = None,
) -> RubricDraftOut:
    criteria, prompt_version = await JobService(db, ctx).draft_rubric(
        job_id, provider, body.jd_text if body else None
    )
    return RubricDraftOut(criteria=criteria, prompt_version=prompt_version)


# PUT /jobs/{id}/rubric -> 200 with the job; 422 if weights don't add up to 100
# PUT = replace the whole sub-resource with what you send. It's idempotent: sending the
# same rubric twice leaves the same result, so retries are safe.
@router.put("/{job_id}/rubric")
async def replace_rubric(job_id: uuid.UUID, body: RubricIn, ctx: Writer, db: DbSession) -> JobOut:
    return JobOut.model_validate(await JobService(db, ctx).replace_rubric(job_id, body))


# POST /jobs/{id}/publish and /close -> 200 with the job; 409 if the move isn't allowed
# State transitions are actions with rules, not field edits, so they get their own
# endpoints instead of PATCH {"status": "open"}. 409 Conflict = your request is fine,
# but it conflicts with the job's current state (e.g. closing a draft).
@router.post("/{job_id}/publish")
async def publish_job(job_id: uuid.UUID, ctx: Writer, db: DbSession) -> JobOut:
    return JobOut.model_validate(await JobService(db, ctx).publish(job_id))


@router.post("/{job_id}/close")
async def close_job(job_id: uuid.UUID, ctx: Writer, db: DbSession) -> JobOut:
    return JobOut.model_validate(await JobService(db, ctx).close(job_id))
