"""Rubric drafting: JD text -> AI-suggested criteria with weights that sum to 100."""

from app.llm.prompts import load_prompt
from app.llm.runner import LLMRunner
from app.llm.schemas import RubricSuggestion
from app.models import LLMPurpose
from app.schemas.jobs import CriterionIn

JD_PARSE_PROMPT = load_prompt("jd_parse", 1)


def normalize_weights(raw: list[int], total: int = 100) -> list[int]:
    """Scale positive integers so they sum to exactly `total`, keeping proportions.

    Uses the largest-remainder method: floor every share, then hand the leftover points
    to the items with the biggest fractional parts. Plain rounding can't guarantee the
    sum: [1, 1, 1] -> 33.33 each -> rounds to 33+33+33 = 99.
    """
    if not raw:
        return []
    if any(w < 0 for w in raw):
        raise ValueError("weights must be non-negative")
    raw_sum = sum(raw)
    if raw_sum == 0:
        raw = [1] * len(raw)  # no signal: split evenly
        raw_sum = len(raw)

    exact = [w * total / raw_sum for w in raw]
    floors = [int(x) for x in exact]
    leftover = total - sum(floors)
    # Indices by largest fractional part; ties go to the earlier (usually more important) item.
    by_remainder = sorted(range(len(raw)), key=lambda i: (-(exact[i] - floors[i]), i))
    for i in by_remainder[:leftover]:
        floors[i] += 1
    return floors


async def suggest_rubric(runner: LLMRunner, jd_text: str) -> list[CriterionIn]:
    """Ask the LLM for a rubric draft. Nothing is saved: the recruiter reviews and edits
    it, then saves with PUT /jobs/{id}/rubric."""
    suggestion = await runner.run(
        purpose=LLMPurpose.JD_PARSE,
        prompt=JD_PARSE_PROMPT,
        variables={"jd_text": jd_text},
        output=RubricSuggestion,
    )
    weights = normalize_weights([c.suggested_weight for c in suggestion.criteria])
    return [
        CriterionIn(
            name=c.name,
            description=c.description,
            type=c.type,
            weight=w,
            is_knockout=c.is_knockout,
        )
        for c, w in zip(suggestion.criteria, weights, strict=True)
    ]
