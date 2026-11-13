"""LLMRunner + rubric drafting against a real DB (llm_calls rows) and a fake LLM."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadGatewayError, GatewayTimeoutError, ServiceUnavailableError
from app.llm.provider import LLMBusyError, LLMProviderError, LLMTimeoutError
from app.llm.runner import LLMRunner
from app.models import LLMCall, LLMPurpose, Organization
from app.services.rubric import suggest_rubric
from tests.fakes import FakeLLMProvider, fixture_text

RECORDED = fixture_text("llm/jd_parse_v1/backend_engineer.json")
JD = fixture_text("jds/backend_engineer.txt")


@pytest.fixture
async def org_id(db_session: AsyncSession) -> uuid.UUID:
    org = Organization(name="LLM Test Org", slug=f"llm-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org.id


async def _calls(db: AsyncSession, org_id: uuid.UUID) -> list[LLMCall]:
    result = await db.execute(
        select(LLMCall).where(LLMCall.org_id == org_id).order_by(LLMCall.created_at)
    )
    return list(result.scalars())


async def test_suggest_rubric_from_recorded_response(
    db_session: AsyncSession, org_id: uuid.UUID
) -> None:
    fake = FakeLLMProvider([RECORDED])
    criteria = await suggest_rubric(LLMRunner(db_session, org_id, fake), JD)

    assert len(criteria) == 8
    assert sum(c.weight for c in criteria) == 100
    assert criteria[0].name == "Backend experience (3+ years)"
    assert [c.is_knockout for c in criteria].count(True) == 3

    # The JD was sent as delimited data, at temperature 0, with a JSON Schema.
    call = fake.calls[0]
    assert JD.strip() in call.user and "<job_description>" in call.user
    assert call.temperature == 0.0
    assert "criteria" in call.json_schema["properties"]

    [row] = await _calls(db_session, org_id)
    assert row.purpose == LLMPurpose.JD_PARSE
    assert row.prompt_version == "jd_parse_v1"
    assert row.model == "gemini-3.5-flash-lite"
    assert (row.input_tokens, row.output_tokens) == (1200, 400)
    assert row.cost_usd > 0
    assert row.success and row.error is None


async def test_invalid_output_gets_one_repair_retry(
    db_session: AsyncSession, org_id: uuid.UUID
) -> None:
    bad = '{"criteria": [{"name": "Python", "type": "wizardry"}]}'
    fake = FakeLLMProvider([bad, RECORDED])
    criteria = await suggest_rubric(LLMRunner(db_session, org_id, fake), JD)

    assert len(criteria) == 8
    assert "did not match the required JSON schema" in fake.calls[1].user
    rows = await _calls(db_session, org_id)
    assert [(r.success, r.error) for r in rows] == [(False, "invalid_output"), (True, None)]


async def test_invalid_output_twice_is_502(db_session: AsyncSession, org_id: uuid.UUID) -> None:
    fake = FakeLLMProvider(["not json", '{"criteria": []}'])
    with pytest.raises(BadGatewayError):
        await suggest_rubric(LLMRunner(db_session, org_id, fake), JD)
    rows = await _calls(db_session, org_id)
    assert [r.error for r in rows] == ["invalid_output", "invalid_output"]


async def test_timeout_is_504_and_still_logged(db_session: AsyncSession, org_id: uuid.UUID) -> None:
    fake = FakeLLMProvider([LLMTimeoutError()])
    with pytest.raises(GatewayTimeoutError):
        await suggest_rubric(LLMRunner(db_session, org_id, fake), JD)
    [row] = await _calls(db_session, org_id)
    assert (row.success, row.error, row.input_tokens) == (False, "timeout", 0)


async def test_provider_error_is_502_and_logged(
    db_session: AsyncSession, org_id: uuid.UUID
) -> None:
    fake = FakeLLMProvider([LLMProviderError("gemini_429")])
    with pytest.raises(BadGatewayError):
        await suggest_rubric(LLMRunner(db_session, org_id, fake), JD)
    [row] = await _calls(db_session, org_id)
    assert row.error == "gemini_429"
    assert len(fake.calls) == 1  # provider errors are not retried here


async def test_rate_limited_is_503_try_again(db_session: AsyncSession, org_id: uuid.UUID) -> None:
    fake = FakeLLMProvider([LLMBusyError("gemini_429")])
    with pytest.raises(ServiceUnavailableError, match="try again"):
        await suggest_rubric(LLMRunner(db_session, org_id, fake), JD)
    [row] = await _calls(db_session, org_id)
    assert row.error == "gemini_429"
