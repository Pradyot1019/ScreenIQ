"""Request/response bodies for jobs and rubrics."""

import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import CriterionType, EmploymentType, Job, JobStatus

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
# A JD shorter than ~50 characters can't produce a meaningful rubric; 20k caps LLM cost.
JDText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=50, max_length=20_000)]
CriterionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]

# ---- rubric ---------------------------------------------------------------------------


class CriterionIn(BaseModel):
    """One rubric line as the recruiter edits it (and as the AI draft returns it)."""

    model_config = ConfigDict(from_attributes=True)

    name: CriterionName
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    type: CriterionType
    weight: int = Field(ge=0, le=100)
    is_knockout: bool = False


class CriterionOut(CriterionIn):
    id: uuid.UUID


class RubricIn(BaseModel):
    """Body of PUT /jobs/{id}/rubric: the complete new rubric (replaces the old one)."""

    criteria: list[CriterionIn] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _weights_sum_to_100_and_names_unique(self) -> Self:
        total = sum(c.weight for c in self.criteria)
        if total != 100:
            raise ValueError(f"Criterion weights must add up to 100 (they add up to {total}).")
        names = [c.name.casefold() for c in self.criteria]
        if len(names) != len(set(names)):
            raise ValueError("Each criterion needs a different name.")
        return self


class RubricDraftIn(BaseModel):
    """Body of POST /jobs/{id}/rubric:generate. Defaults to the job's own description."""

    jd_text: JDText | None = None


class RubricDraftOut(BaseModel):
    criteria: list[CriterionIn]
    prompt_version: str


# ---- jobs -----------------------------------------------------------------------------


class JobCreate(BaseModel):
    title: Title
    department: ShortText | None = None
    location: ShortText | None = None
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    description: JDText
    blind_mode: bool = False


class JobUpdate(BaseModel):
    """PATCH body: only the fields you send are changed. Status is NOT editable here;
    it moves only through /publish and /close, so the rules live in one place."""

    # Unknown fields (e.g. "status") are a 422, not silently ignored: a client that
    # thinks it changed the status should find out that it didn't.
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    department: ShortText | None = None
    location: ShortText | None = None
    employment_type: EmploymentType | None = None
    description: JDText | None = None
    blind_mode: bool | None = None

    @model_validator(mode="after")
    def _required_fields_not_null(self) -> Self:
        # department/location may be cleared with null; these may not.
        for name in ("title", "employment_type", "description", "blind_mode"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        return self


class JobSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    employment_type: EmploymentType
    status: JobStatus
    slug: str
    created_at: datetime
    criteria_count: int

    @classmethod
    def from_job(cls, job: Job) -> Self:
        return cls(
            id=job.id,
            title=job.title,
            department=job.department,
            location=job.location,
            employment_type=job.employment_type,
            status=job.status,
            slug=job.slug,
            created_at=job.created_at,
            criteria_count=len(job.criteria),
        )


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    employment_type: EmploymentType
    description: str
    status: JobStatus
    slug: str
    blind_mode: bool
    created_by: uuid.UUID | None
    created_at: datetime
    criteria: list[CriterionOut]


class JobPage(BaseModel):
    items: list[JobSummaryOut]
    next_cursor: str | None = Field(
        description="Pass as ?cursor= to get the next page; null = last page"
    )
