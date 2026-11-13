"""Turning per-criterion results into the final screening (FR-31 to FR-34).

Deterministic on purpose: the LLM judges each criterion; plain code (that you can read
and unit-test) does the arithmetic. Same inputs, same score, every time.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.models import Recommendation
from app.pipeline.evidence import check_evidence

NO_EVIDENCE_MAX = 3  # spec 9.2: no evidence -> score <= 3
KNOCKOUT_PASS = 5  # a knockout criterion scoring below this counts as "not met"
STRONG_AT = Decimal(75)
POSSIBLE_AT = Decimal(50)


@dataclass(frozen=True)
class CriterionInput:
    """A criterion as scored by the LLM, before checks."""

    name: str
    weight: int
    is_knockout: bool
    score: int
    reasoning: str
    evidence: list[str]


@dataclass(frozen=True)
class CriterionResult:
    name: str
    weight: int
    is_knockout: bool
    score: int
    reasoning: str
    evidence: list[str]
    rejected_evidence: list[str]
    low_confidence: bool


def verify_criterion(c: CriterionInput, resume_text: str) -> CriterionResult:
    checked = check_evidence(c.evidence, resume_text)
    score = max(0, min(10, c.score))  # clamp: never trust a number blindly
    low_confidence = bool(checked.rejected)  # FR-32: a quote didn't match the resume
    if not checked.verified and score > NO_EVIDENCE_MAX:
        score = NO_EVIDENCE_MAX  # a high score with nothing to back it isn't allowed
        low_confidence = True
    return CriterionResult(
        name=c.name,
        weight=c.weight,
        is_knockout=c.is_knockout,
        score=score,
        reasoning=c.reasoning,
        evidence=checked.verified,
        rejected_evidence=checked.rejected,
        low_confidence=low_confidence,
    )


def overall_score(results: list[CriterionResult]) -> Decimal:
    """Weighted average on a 0-100 scale. Weights total 100 (enforced when saving)."""
    total_weight = sum(r.weight for r in results)
    if total_weight == 0:
        return Decimal(0)
    raw = sum((Decimal(r.score) / 10 * r.weight for r in results), Decimal(0)) * 100 / total_weight
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def knockout_failed(results: list[CriterionResult]) -> bool:
    return any(r.is_knockout and r.score < KNOCKOUT_PASS for r in results)


def recommend(score: Decimal, knocked_out: bool) -> Recommendation:
    """A label for humans, never an action: nothing here rejects anyone (FR-38)."""
    if knocked_out:
        return Recommendation.WEAK
    if score >= STRONG_AT:
        return Recommendation.STRONG
    if score >= POSSIBLE_AT:
        return Recommendation.POSSIBLE
    return Recommendation.WEAK
