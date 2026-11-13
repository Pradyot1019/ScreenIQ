"""Output schemas for LLM calls. These become the JSON Schema the model must follow,
and the Pydantic validation applied to its reply."""

from typing import Annotated

from pydantic import BaseModel, Field

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
