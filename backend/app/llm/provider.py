"""The LLMProvider interface: the only thing the rest of the app knows about LLMs.

A provider is pure transport: send a prompt plus a JSON Schema, get back raw JSON text
and token counts. Validation, retries, cost and logging live in `runner.py`, so they
work the same for every provider. Swapping Gemini for Claude/OpenAI/a local model means
writing one new class with `generate_json`, and nothing else changes.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError


@dataclass(frozen=True)
class LLMResponse:
    text: str  # raw model output, expected to be JSON
    model: str  # the exact model version that answered
    input_tokens: int
    output_tokens: int  # everything billed as output, including hidden "thinking" tokens


class LLMTimeoutError(Exception):
    """The provider didn't answer within the timeout."""


class LLMProviderError(Exception):
    """The provider returned an error (bad key, outage...)."""


class LLMBusyError(LLMProviderError):
    """Rate-limited (429) or overloaded (503). Retrying later can succeed.

    Common on free tiers, so it gets its own type: the API answers 503 with a
    "try again" message instead of a generic 502.
    """


class LLMProvider(Protocol):
    @property
    def model(self) -> str: ...

    async def generate_json(
        self, *, system: str, user: str, json_schema: dict[str, Any], temperature: float
    ) -> LLMResponse:
        """Raises LLMTimeoutError or LLMProviderError; never returns partial results."""
        ...


_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """FastAPI dependency. One shared client per process (it holds a connection pool).

    Tests override this dependency with a fake that replays recorded responses.
    """
    global _provider
    if _provider is None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ServiceUnavailableError(
                "AI features aren't configured on this server (GEMINI_API_KEY is not set)."
            )
        from app.llm.gemini import GeminiProvider  # imported lazily: heavy SDK

        _provider = GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
        )
    return _provider
