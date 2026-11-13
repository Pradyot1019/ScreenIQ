"""ARQ worker entrypoint. Run with:  arq app.workers.arq_worker.WorkerSettings

Tasks: parse_resume -> (auto) screen_application. Both share one policy:
- transient errors (LLM busy/timeout, storage hiccup) -> retry with backoff, 3 tries;
- after the last try, or on any unexpected error -> mark failed with a readable reason,
  so nothing is ever stuck "in progress" and polling UIs always finish.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from arq import Retry
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.llm.provider import LLMProvider, get_llm_provider
from app.models import Application
from app.services.intake import ResumeParser, TransientParseError
from app.services.screening import ScreeningRunner, queue_screening
from app.storage.s3 import get_storage

logger = logging.getLogger(__name__)
MAX_TRIES = 3  # spec NFR: 3 attempts with backoff
NO_KEY = "AI isn't configured on the server (no API key)."


async def ping(ctx: dict[str, Any]) -> str:
    return "pong"


async def _with_retries(
    ctx: dict[str, Any],
    task: str,
    item_id: str,
    work: Callable[[LLMProvider], Awaitable[None]],
    fail: Callable[[str], Awaitable[None]],
    session: AsyncSession,
) -> None:
    try:
        provider = get_llm_provider()
    except ServiceUnavailableError:
        await fail(NO_KEY)
        return
    try:
        await work(provider)
    except TransientParseError as e:
        attempt = ctx["job_try"]
        if attempt >= MAX_TRIES:
            await fail("The AI service was busy. Please try again later.")
            return
        delay = 15 * 2 ** (attempt - 1)  # 15s, 30s: exponential backoff
        logger.warning(
            f"{task}_retry",
            extra={"extra_fields": {"id": item_id, "attempt": attempt, "why": str(e)}},
        )
        raise Retry(defer=delay) from e
    except Exception:
        # ARQ doesn't retry unknown errors. Without this the item would sit "in progress"
        # forever and the UI would poll forever.
        logger.exception(f"{task}_crashed", extra={"extra_fields": {"id": item_id}})
        await session.rollback()
        await fail("Something went wrong. Please try again.")


async def parse_resume(ctx: dict[str, Any], resume_id: str) -> None:
    rid = uuid.UUID(resume_id)
    async with SessionLocal() as session:
        storage = get_storage()

        async def work(provider: LLMProvider) -> None:
            application_id = await ResumeParser(session, storage, provider).run(rid)
            if application_id is not None:
                await _queue_screening(ctx, session, application_id)

        async def fail(reason: str) -> None:
            if reason == NO_KEY:
                reason = "AI parsing isn't configured on the server (no API key)."
            await ResumeParser(session, storage).fail(rid, reason)

        await _with_retries(ctx, "resume_parse", resume_id, work, fail, session)


async def _queue_screening(
    ctx: dict[str, Any], session: AsyncSession, application_id: uuid.UUID
) -> None:
    """Parsed -> screen automatically, if the job already has a complete rubric."""
    application = await session.get(Application, application_id)
    if application is None:
        return
    screening = await queue_screening(session, application.org_id, application)
    if screening is None:
        return  # no rubric yet; the recruiter can "screen pending" after saving one
    await session.commit()
    await ctx["redis"].enqueue_job(
        "screen_application", str(screening.id), _job_id=f"screen:{screening.id}"
    )


async def screen_application(ctx: dict[str, Any], screening_id: str) -> None:
    sid = uuid.UUID(screening_id)
    async with SessionLocal() as session:

        async def work(provider: LLMProvider) -> None:
            await ScreeningRunner(session, provider).run(sid)

        async def fail(reason: str) -> None:
            await ScreeningRunner(session).fail(sid, reason)

        await _with_retries(ctx, "screening", screening_id, work, fail, session)


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(get_settings().log_level)


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ping, parse_resume, screen_application]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_TRIES
    job_timeout = 180
    max_jobs = 4  # gentle on the free-tier LLM rate limit
