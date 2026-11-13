"""Resume upload and batch progress (FR-20, FR-25)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.core.deps import CurrentOrg, DbSession, OrgContext, require_role
from app.core.errors import NotFoundError
from app.models import Batch, Role
from app.pipeline.extract import MAX_FILE_BYTES
from app.repositories.intake import BatchRepository, ResumeRepository
from app.schemas.intake import BatchFileOut, BatchOut
from app.services.intake import IntakeService
from app.storage.s3 import Storage, get_storage
from app.workers.queue import Queue, get_queue

router = APIRouter(tags=["resumes"])

Writer = Annotated[OrgContext, Depends(require_role(Role.OWNER, Role.RECRUITER))]


async def _batch_out(db: DbSession, org_id: uuid.UUID, batch: Batch) -> BatchOut:
    rows = await ResumeRepository(db, org_id).list_for_batch(batch.id)
    return BatchOut(
        id=batch.id,
        job_id=batch.job_id,
        status=batch.status,
        total=batch.total,
        processed=batch.processed,
        failed=batch.failed,
        created_at=batch.created_at,
        files=[
            BatchFileOut(
                resume_id=r.id,
                filename=r.filename,
                status=r.parse_status,
                error=r.error,
                candidate_id=c.id if c else None,
                candidate_name=c.full_name if c else None,
            )
            for r, c in rows
        ],
    )


# POST /jobs/{id}/resumes (multipart, field "files") -> 202 Accepted + Location: /batches/{id}
# 202 = "received, work continues in the background": parsing takes seconds per file.
@router.post("/jobs/{job_id}/resumes", status_code=status.HTTP_202_ACCEPTED)
async def upload_resumes(
    job_id: uuid.UUID,
    ctx: Writer,
    db: DbSession,
    response: Response,
    storage: Annotated[Storage, Depends(get_storage)],
    queue: Annotated[Queue, Depends(get_queue)],
    files: Annotated[list[UploadFile], File(description="1-50 PDF/DOCX files, 5 MB each")],
) -> BatchOut:
    # Read at most 5 MB + 1 byte per file: enough to detect "too big" without buffering more.
    contents = [(f.filename or "resume", await f.read(MAX_FILE_BYTES + 1)) for f in files]
    batch, queued = await IntakeService(db, ctx, storage).upload(job_id, contents)
    for resume_id in queued:  # enqueue only after commit, so the worker can see the rows
        await queue.enqueue("parse_resume", str(resume_id), job_id=f"parse:{resume_id}")
    response.headers["Location"] = f"/api/v1/batches/{batch.id}"
    return await _batch_out(db, ctx.org_id, batch)


# GET /batches/{id} -> 200 progress + per-file status; the UI polls this.
@router.get("/batches/{batch_id}")
async def get_batch(batch_id: uuid.UUID, ctx: CurrentOrg, db: DbSession) -> BatchOut:
    db.expire_all()  # always read fresh counters written by the worker
    batch = await BatchRepository(db, ctx.org_id).get(batch_id)
    if batch is None:
        raise NotFoundError("Batch not found.")
    return await _batch_out(db, ctx.org_id, batch)
