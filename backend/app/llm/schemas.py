"""Output schemas for LLM calls. These become the JSON Schema the model must follow,
and the Pydantic validation applied to its reply."""

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
