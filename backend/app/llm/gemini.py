"""Gemini implementation of LLMProvider, using Google's `google-genai` SDK."""

import asyncio
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.llm.provider import LLMBusyError, LLMProviderError, LLMResponse, LLMTimeoutError


class GeminiProvider:
    def __init__(self, *, api_key: str, model: str, timeout_s: float) -> None:
        self._model = model
        self._timeout_s = timeout_s
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )

    @property
    def model(self) -> str:
        return self._model

    async def generate_json(
        self, *, system: str, user: str, json_schema: dict[str, Any], temperature: float
    ) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            # Structured output: the model is constrained to emit JSON matching this
            # schema. We still validate with Pydantic afterwards; constrained decoding
            # makes invalid output rare, not impossible.
            response_mime_type="application/json",
            response_json_schema=json_schema,
        )
        try:
            # wait_for is a hard ceiling on top of the HTTP timeout (covers retries too).
            resp = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._model, contents=user, config=config
                ),
                timeout=self._timeout_s,
            )
        except (TimeoutError, httpx.TimeoutException) as e:
            raise LLMTimeoutError from e
        except genai_errors.APIError as e:
            # e.code is the HTTP status (400 bad request, 403 bad key, 404 retired model,
            # 429 rate limit, 503 overloaded...).
            if e.code in (429, 503):
                raise LLMBusyError(f"gemini_{e.code}") from e
            raise LLMProviderError(f"gemini_{e.code}") from e
        except httpx.HTTPError as e:
            raise LLMProviderError("gemini_network") from e

        usage = resp.usage_metadata
        input_tokens = (usage.prompt_token_count or 0) if usage else 0
        # Gemini 2.5+ "thinks" before answering; thinking tokens are billed as output.
        output_tokens = (
            ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0))
            if usage
            else 0
        )
        return LLMResponse(
            text=resp.text or "",
            model=resp.model_version or self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
