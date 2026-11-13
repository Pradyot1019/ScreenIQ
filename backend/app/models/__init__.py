"""Import every model module here so Alembic autogenerate can see them."""

from app.models.activity import Note, StageEvent
from app.models.candidate import (
    Application,
    ApplicationSource,
    Batch,
    BatchStatus,
    Candidate,
    ParseStatus,
    Resume,
    Stage,
)
from app.models.job import CriterionType, EmploymentType, Job, JobStatus, RubricCriterion
from app.models.llm_call import LLMCall, LLMPurpose
from app.models.organization import Membership, Organization, Plan, Role
from app.models.refresh_token import RefreshToken
from app.models.screening import CriterionScore, Recommendation, Screening, ScreeningStatus
from app.models.user import User

__all__ = [
    "Application",
    "ApplicationSource",
    "Batch",
    "BatchStatus",
    "Candidate",
    "ParseStatus",
    "Resume",
    "Stage",
    "StageEvent",
    "CriterionScore",
    "CriterionType",
    "EmploymentType",
    "Job",
    "JobStatus",
    "LLMCall",
    "LLMPurpose",
    "Membership",
    "Note",
    "Organization",
    "Plan",
    "Recommendation",
    "RefreshToken",
    "Role",
    "RubricCriterion",
    "Screening",
    "ScreeningStatus",
    "User",
]
