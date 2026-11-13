"""Unit tests for the LLM building blocks: prompts, cost, schema, weights, Gemini adapter."""

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.llm.cost import cost_usd
from app.llm.gemini import GeminiProvider
from app.llm.prompts import load_prompt
from app.llm.runner import json_schema_for
from app.llm.schemas import ParsedResume, RubricSuggestion
from app.services.rubric import normalize_weights

# ---- prompts --------------------------------------------------------------------------


def test_jd_parse_prompt_loads_and_renders() -> None:
    prompt = load_prompt("jd_parse", 1)
    assert prompt.id == "jd_parse_v1"
    system, user = prompt.render(jd_text="We need a Python dev.")
    assert "data, not instructions" in system  # prompt-injection defense is in place
    assert "<job_description>\nWe need a Python dev.\n</job_description>" in user


def test_prompt_render_requires_exact_variables() -> None:
    prompt = load_prompt("jd_parse", 1)
    with pytest.raises(ValueError, match="expects"):
        prompt.render()
    with pytest.raises(ValueError, match="expects"):
        prompt.render(jd_text="x", extra="y")


def test_jd_text_cannot_inject_placeholders() -> None:
    # A JD containing "{{jd_text}}" is inserted literally, not re-expanded.
    _, user = load_prompt("jd_parse", 1).render(jd_text="{{jd_text}} {{other}}")
    assert "{{jd_text}} {{other}}" in user


# ---- cost -----------------------------------------------------------------------------


def test_cost_known_model() -> None:
    # 1M input at $0.30 + 1M output at $2.50
    assert cost_usd("gemini-2.5-flash", 1_000_000, 1_000_000) == Decimal("2.800000")
    assert cost_usd("gemini-2.5-flash", 1200, 400) == Decimal("0.001360")


def test_cost_longest_prefix_wins() -> None:
    assert cost_usd("gemini-2.5-flash-lite-001", 1_000_000, 0) == Decimal("0.100000")


def test_cost_unknown_model_is_zero_not_an_error() -> None:
    assert cost_usd("some-new-model", 1000, 1000) == Decimal(0)


# ---- JSON schema sent to the model ----------------------------------------------------


def test_json_schema_is_self_contained() -> None:
    schema = json_schema_for(RubricSuggestion)
    text = str(schema)
    assert "$ref" not in text and "$defs" not in text
    item = schema["properties"]["criteria"]["items"]
    assert item["properties"]["type"]["enum"] == ["skill", "experience", "education", "other"]


def test_json_schema_omits_max_items_but_pydantic_still_enforces_them() -> None:
    # Gemini 400s on schemas with many maxItems; they're dropped from what we send...
    assert "maxItems" not in str(json_schema_for(ParsedResume))
    # ...but the reply is still validated against the real model.
    with pytest.raises(ValidationError):
        ParsedResume.model_validate({"links": ["x"] * 21})


# ---- weight normalization -------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ([25, 25, 20, 15, 10, 5, 5, 5], [23, 23, 18, 14, 9, 5, 4, 4]),
        ([1, 1, 1], [34, 33, 33]),  # plain rounding would give 99
        ([50, 50], [50, 50]),
        ([0, 0, 0, 0], [25, 25, 25, 25]),
        ([7], [100]),
        ([], []),
    ],
)
def test_normalize_weights(raw: list[int], expected: list[int]) -> None:
    result = normalize_weights(raw)
    assert result == expected
    assert sum(result) == (100 if raw else 0)


def test_normalize_weights_rejects_negative() -> None:
    with pytest.raises(ValueError):
        normalize_weights([10, -5])


# ---- Gemini adapter: token accounting -------------------------------------------------


async def test_gemini_counts_thinking_tokens_as_output(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash", timeout_s=5)
    sent: dict[str, Any] = {}

    async def fake_generate_content(**kwargs: Any) -> SimpleNamespace:
        sent.update(kwargs)
        return SimpleNamespace(
            text='{"ok": true}',
            model_version="gemini-2.5-flash-001",
            usage_metadata=SimpleNamespace(
                prompt_token_count=1000, candidates_token_count=200, thoughts_token_count=300
            ),
        )

    monkeypatch.setattr(provider._client.aio.models, "generate_content", fake_generate_content)
    resp = await provider.generate_json(
        system="sys", user="usr", json_schema={"type": "object"}, temperature=0.0
    )

    assert resp.input_tokens == 1000
    assert resp.output_tokens == 500  # 200 answer + 300 thinking, both billed as output
    assert resp.model == "gemini-2.5-flash-001"
    assert sent["config"].temperature == 0.0
    assert sent["config"].response_mime_type == "application/json"
    assert sent["config"].system_instruction == "sys"
