import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

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


class ApplicationDetail(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    stage: Stage
    created_at: datetime
    candidate: CandidateBrief
    profile: dict[str, Any]  # the parsed resume (ParsedResume as JSON)
    screening: ScreeningOut | None


class ScreeningQueued(BaseModel):
    queued: int
