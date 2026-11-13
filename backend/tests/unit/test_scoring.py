"""Evidence matching and deterministic scoring (FR-31 to FR-34)."""

from decimal import Decimal

import pytest

from app.models import Recommendation
from app.pipeline.evidence import check_evidence
from app.pipeline.score import (
    CriterionInput,
    CriterionResult,
    knockout_failed,
    overall_score,
    recommend,
    verify_criterion,
)

RESUME = """Senior Software Engineer, Lumen Logistics (Jan 2022 - Present)
- Built FastAPI services handling 2M requests/day with p95
latency under 120 ms
- Designed PostgreSQL schemas and cut slow-query time by 60%"""


# ---- evidence -------------------------------------------------------------------------


def test_exact_and_reflowed_quotes_are_verified() -> None:
    check = check_evidence(
        [
            "Designed PostgreSQL schemas",
            # The PDF broke this sentence across lines; the quote doesn't have the break.
            "Built FastAPI services handling 2M requests/day with p95 latency under 120 ms",
            "“Built FastAPI services”",  # curly quotes from the model
        ],
        RESUME,
    )
    assert len(check.verified) == 3 and check.rejected == []


def test_made_up_and_too_short_quotes_are_rejected() -> None:
    check = check_evidence(["Led a team of 12 engineers at Google", "Go"], RESUME)
    assert check.verified == []
    assert check.rejected == ["Led a team of 12 engineers at Google", "Go"]


def test_paraphrase_is_not_evidence() -> None:
    check = check_evidence(["Created Postgres databases and made queries faster"], RESUME)
    assert check.verified == []


# ---- per-criterion checks -------------------------------------------------------------


def _input(score: int, evidence: list[str], knockout: bool = False) -> CriterionInput:
    return CriterionInput("Python", 50, knockout, score, "reason", evidence)


def test_high_score_without_real_evidence_is_capped_at_3() -> None:
    r = verify_criterion(_input(10, ["Principal Engineer at Google since 2012"]), RESUME)
    assert (r.score, r.low_confidence) == (3, True)
    assert r.evidence == [] and r.rejected_evidence == ["Principal Engineer at Google since 2012"]


def test_one_bad_quote_flags_low_confidence_but_keeps_the_score() -> None:
    r = verify_criterion(_input(8, ["Designed PostgreSQL schemas", "Built rockets"]), RESUME)
    assert (r.score, r.low_confidence) == (8, True)
    assert r.evidence == ["Designed PostgreSQL schemas"]


def test_honest_low_score_without_evidence_is_not_flagged() -> None:
    r = verify_criterion(_input(2, []), RESUME)
    assert (r.score, r.low_confidence) == (2, False)


# ---- aggregation ----------------------------------------------------------------------


def _result(score: int, weight: int, knockout: bool = False) -> CriterionResult:
    return CriterionResult("x", weight, knockout, score, "", [], [], False)


def test_overall_is_weighted_average_on_0_to_100() -> None:
    results = [_result(9, 50), _result(9, 30), _result(8, 20)]
    assert overall_score(results) == Decimal("88.00")
    assert overall_score([_result(10, 100)]) == Decimal("100.00")
    assert overall_score([_result(0, 60), _result(5, 40)]) == Decimal("20.00")


def test_knockout_fails_below_5() -> None:
    assert knockout_failed([_result(4, 50, knockout=True), _result(10, 50)])
    assert not knockout_failed([_result(5, 50, knockout=True), _result(0, 50)])


@pytest.mark.parametrize(
    ("score", "knocked_out", "expected"),
    [
        (Decimal("88"), False, Recommendation.STRONG),
        (Decimal("75"), False, Recommendation.STRONG),
        (Decimal("74.99"), False, Recommendation.POSSIBLE),
        (Decimal("50"), False, Recommendation.POSSIBLE),
        (Decimal("49.99"), False, Recommendation.WEAK),
        (Decimal("95"), True, Recommendation.WEAK),  # a failed must-have caps it
    ],
)
def test_recommendation_thresholds(
    score: Decimal, knocked_out: bool, expected: Recommendation
) -> None:
    assert recommend(score, knocked_out) == expected
