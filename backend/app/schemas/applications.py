import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models import Recommendation, ScreeningStatus, Stage


class CandidateBrief(BaseModel):
    id: uuid.UUID
    full_name: str | None
    email: str | None
    total_experience_years: Decimal | None


class ScreeningBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ScreeningStatus
    overall_score: Decimal | None
    recommendation: Recommendation | None
    knockout_failed: bool | None


class ApplicationRow(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    stage: Stage
    created_at: datetime
    candidate: CandidateBrief
    screening: ScreeningBrief | None


class CriterionScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    criterion_name: str
    weight: int
    is_knockout: bool
    score: int
    reasoning: str
    evidence: list[str]
    rejected_evidence: list[str]
    low_confidence: bool


class ScreeningOut(ScreeningBrief):
    summary: str | None
    strengths: list[str]
    gaps: list[str]
    model: str | None
    prompt_version: str | None
    error: str | None
    created_at: datetime
    criterion_scores: list[CriterionScoreOut]


class StageEventOut(BaseModel):
    from_stage: Stage
    to_stage: Stage
    actor_name: str | None  # None = the system (AI screening)
    created_at: datetime


class ApplicationDetail(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    stage: Stage
    created_at: datetime
    candidate: CandidateBrief
    profile: dict[str, Any]  # the parsed resume (ParsedResume as JSON)
    screening: ScreeningOut | None
    history: list[StageEventOut]


class StageIn(BaseModel):
    stage: Stage


class NoteIn(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class NoteOut(BaseModel):
    id: uuid.UUID
    body: str
    author_name: str | None
    created_at: datetime


class HighlightOut(BaseModel):
    start: int
    end: int
    criterion: str


class ResumeView(BaseModel):
    filename: str
    mime_type: str
    url: str | None  # short-lived signed URL for the original file
    url_expires_in: int
    text: str
    highlights: list[HighlightOut]


class CompareCandidate(BaseModel):
    application_id: uuid.UUID
    name: str | None
    stage: Stage
    overall_score: Decimal | None
    recommendation: Recommendation | None
    knockout_failed: bool | None
    scores: dict[str, int]  # criterion name -> 0-10
    low_confidence: list[str]  # criterion names flagged low confidence


class CompareOut(BaseModel):
    criteria: list[str]
    candidates: list[CompareCandidate]


class ScreeningQueued(BaseModel):
    queued: int
