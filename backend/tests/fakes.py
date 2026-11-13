"""FakeLLMProvider: replays recorded LLM responses so tests are fast, free and deterministic.

Each queued item is either a response text (usually loaded from tests/fixtures/llm/)
or an exception to raise. Every call is recorded so tests can assert on the prompt
that was sent.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.llm.provider import LLMResponse

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(relative_path: str) -> str:
    return (FIXTURES / relative_path).read_text(encoding="utf-8")


@dataclass
class FakeCall:
    system: str
    user: str
    json_schema: dict[str, Any]
    temperature: float


@dataclass
class FakeLLMProvider:
    replies: list[str | Exception]
    model_name: str = "gemini-3.5-flash-lite"
    input_tokens: int = 1200
    output_tokens: int = 400
    calls: list[FakeCall] = field(default_factory=list)

    @property
    def model(self) -> str:
        return self.model_name

    async def generate_json(
        self, *, system: str, user: str, json_schema: dict[str, Any], temperature: float
    ) -> LLMResponse:
        self.calls.append(FakeCall(system, user, json_schema, temperature))
        if not self.replies:
            raise AssertionError("FakeLLMProvider: no more queued replies")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return LLMResponse(
            text=reply,
            model=self.model_name,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )
