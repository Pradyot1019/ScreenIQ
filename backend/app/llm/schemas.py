"""Output schemas for LLM calls. These become the JSON Schema the model must follow,
and the Pydantic validation applied to its reply."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, create_model, model_validator

from app.models import CriterionType


class CriterionSuggestion(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(max_length=500)
    type: CriterionType
    suggested_weight: int = Field(ge=1, le=100)
    is_knockout: bool


class RubricSuggestion(BaseModel):
    """Output of the jd_parse prompt."""

    criteria: list[CriterionSuggestion] = Field(min_length=1, max_length=12)


# ---- resume_parse (FR-23) ---------------------------------------------------------------

DateText = Annotated[str, Field(max_length=10, description='"YYYY-MM", "YYYY" or "present"')]


class Education(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start: DateText | None = None
    end: DateText | None = None


class Experience(BaseModel):
    company: str | None = None
    role: str | None = None
    start: DateText | None = None
    end: DateText | None = None
    bullets: list[str] = Field(default_factory=list, max_length=40)


class Project(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list, max_length=30)


class ParsedResume(BaseModel):
    """Output of the resume_parse prompt; stored as candidates.parsed (JSONB)."""

    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    links: list[str] = Field(default_factory=list, max_length=20)
    education: list[Education] = Field(default_factory=list, max_length=20)
    experience: list[Experience] = Field(default_factory=list, max_length=40)
    skills: list[str] = Field(default_factory=list, max_length=150)
    projects: list[Project] = Field(default_factory=list, max_length=40)
    certifications: list[str] = Field(default_factory=list, max_length=50)
    total_experience_years: float | None = Field(default=None, ge=0, le=60)


# ---- screen (FR-31, FR-34) --------------------------------------------------------------


class CriterionVerdict(BaseModel):
    key: str
    score: int = Field(ge=0, le=10)
    reasoning: str = Field(max_length=600)
    evidence: list[str] = Field(default_factory=list, max_length=3)


class ScreeningResult(BaseModel):
    """Output of the screen prompt. Checked against the rubric's keys by make_screening_model."""

    criteria: list[CriterionVerdict]
    strengths: list[str] = Field(default_factory=list, max_length=3)
    gaps: list[str] = Field(default_factory=list, max_length=3)
    summary: str = Field(max_length=400)


def make_screening_model(keys: list[str]) -> type[ScreeningResult]:
    """A ScreeningResult subclass for one rubric: `key` must be one of this rubric's keys,
    and every key must appear exactly once. Both go into the JSON Schema (an enum the model
    is constrained to) and the validation, so a skipped or invented criterion triggers
    the repair retry."""
    key_enum: Any = Literal[tuple(keys)]  # built at runtime from this rubric
    verdict = create_model("CriterionVerdict", __base__=CriterionVerdict, key=(key_enum, ...))

    class _Result(ScreeningResult):
        criteria: list[verdict]  # type: ignore[assignment]  # narrows `key` to this rubric

        @model_validator(mode="after")
        def _every_key_once(self) -> "_Result":
            got = sorted(c.key for c in self.criteria)
            if got != sorted(keys):
                raise ValueError(f"criteria must contain each of {keys} exactly once, got {got}")
            return self

    _Result.__name__ = "ScreeningResult"
    return _Result
