"""LLMRunner: every LLM call in the app goes through `run()`.

It adds, on top of any provider:
1. Structured output: the Pydantic model becomes a JSON Schema sent to the provider,
   and the reply is validated against the same model.
2. One repair retry (spec 9.3): if the reply doesn't validate, ask once more and
   say what was wrong. Two strikes -> 502.
3. Logging: one llm_calls row per attempt (model, prompt version, tokens, cost,
   latency, success). Committed immediately, so the cost is recorded even if the
   request fails afterwards.
4. Error mapping: timeout -> 504, rate-limited/overloaded -> 503, other errors -> 502.
"""

import logging
import time
import uuid
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadGatewayError, GatewayTimeoutError, ServiceUnavailableError
from app.llm.cost import cost_usd
from app.llm.prompts import Prompt
from app.llm.provider import (
    LLMBusyError,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    LLMTimeoutError,
)
from app.models import LLMCall, LLMPurpose

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2  # first try + one repair retry


def json_schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic's JSON Schema with every $ref inlined.

    Pydantic puts nested models/enums under "$defs" and points at them with "$ref".
    Inlining keeps the schema self-contained, which LLM structured-output modes
    handle most reliably.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    resolved: dict[str, Any] = resolve(schema)
    return resolved


class LLMRunner:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID, provider: LLMProvider) -> None:
        self.session = session
        self.org_id = org_id
        self.provider = provider

    async def run[T: BaseModel](
        self,
        *,
        purpose: LLMPurpose,
        prompt: Prompt,
        variables: dict[str, str],
        output: type[T],
        temperature: float = 0.0,
    ) -> T:
        system, user = prompt.render(**variables)
        schema = json_schema_for(output)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            start = time.perf_counter()
            try:
                resp = await self.provider.generate_json(
                    system=system, user=user, json_schema=schema, temperature=temperature
                )
            except LLMTimeoutError as e:
                await self._log(purpose, prompt, start, None, error="timeout")
                raise GatewayTimeoutError("The AI service took too long. Please try again.") from e
            except LLMBusyError as e:
                await self._log(purpose, prompt, start, None, error=str(e))
                raise ServiceUnavailableError(
                    "The AI service is busy or rate-limited. Please try again in a minute."
                ) from e
            except LLMProviderError as e:
                await self._log(purpose, prompt, start, None, error=str(e))
                raise BadGatewayError("The AI service returned an error. Please try again.") from e

            try:
                result = output.model_validate_json(resp.text)
            except ValidationError as e:
                await self._log(purpose, prompt, start, resp, error="invalid_output")
                if attempt == MAX_ATTEMPTS:
                    raise BadGatewayError(
                        "The AI returned an invalid response twice. Please try again."
                    ) from e
                # Repair retry: tell the model what was wrong (field paths and messages
                # only, never echoing its output back into logs).
                problems = "; ".join(
                    f"{'.'.join(map(str, err['loc'])) or '(root)'}: {err['msg']}"
                    for err in e.errors()[:5]
                )
                user = (
                    f"{user}\n\nYour previous reply did not match the required JSON schema "
                    f"({problems}). Reply again with valid JSON only."
                )
                continue

            await self._log(purpose, prompt, start, resp, error=None)
            return result

        raise AssertionError("unreachable")  # the loop always returns or raises

    async def _log(
        self,
        purpose: LLMPurpose,
        prompt: Prompt,
        start: float,
        resp: LLMResponse | None,
        *,
        error: str | None,
    ) -> None:
        model = resp.model if resp else self.provider.model
        input_tokens = resp.input_tokens if resp else 0
        output_tokens = resp.output_tokens if resp else 0
        row = LLMCall(
            org_id=self.org_id,
            purpose=purpose,
            model=model,
            prompt_version=prompt.id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd(model, input_tokens, output_tokens),
            latency_ms=round((time.perf_counter() - start) * 1000),
            success=error is None,
            error=error,
        )
        self.session.add(row)
        await self.session.commit()
        logger.info(
            "llm_call",
            extra={
                "extra_fields": {
                    "purpose": purpose.value,
                    "prompt": prompt.id,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": str(row.cost_usd),
                    "latency_ms": row.latency_ms,
                    "success": row.success,
                    "error": error,
                }
            },
        )
