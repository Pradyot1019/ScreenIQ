import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import BatchStatus, ParseStatus


class BatchFileOut(BaseModel):
    resume_id: uuid.UUID
    filename: str
    status: ParseStatus
    error: str | None
    candidate_id: uuid.UUID | None
    candidate_name: str | None


class BatchOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: BatchStatus
    total: int
    processed: int
    failed: int
    created_at: datetime
    files: list[BatchFileOut]
