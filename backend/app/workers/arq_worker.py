"""ARQ worker entrypoint. Run with:  arq app.workers.arq_worker.WorkerSettings"""

import logging
import uuid
from typing import Any, ClassVar

from arq import Retry
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.llm.provider import get_llm_provider
from app.services.intake import ResumeParser, TransientParseError
from app.storage.s3 import get_storage

logger = logging.getLogger(__name__)
MAX_TRIES = 3  # spec NFR: 3 attempts with backoff


async def ping(ctx: dict[str, Any]) -> str:
    return "pong"


async def parse_resume(ctx: dict[str, Any], resume_id: str) -> None:
    rid = uuid.UUID(resume_id)
    async with SessionLocal() as session:
        try:
            provider = get_llm_provider()
        except ServiceUnavailableError:
            await ResumeParser(session, get_storage()).fail(
                rid, "AI parsing isn't configured on the server (no API key)."
            )
            return
        parser = ResumeParser(session, get_storage(), provider)
        try:
            await parser.run(rid)
        except TransientParseError as e:
            attempt = ctx["job_try"]
            if attempt >= MAX_TRIES:
                await parser.fail(rid, "The AI service was busy. Please re-upload this file later.")
                return
            delay = 15 * 2 ** (attempt - 1)  # 15s, 30s: exponential backoff
            logger.warning(
                "resume_parse_retry",
                extra={"extra_fields": {"resume_id": resume_id, "attempt": attempt, "why": str(e)}},
            )
            raise Retry(defer=delay) from e
        except Exception:
            # ARQ doesn't retry unknown errors. Without this the file would sit in
            # "parsing" forever and the upload page would poll forever.
            logger.exception(
                "resume_parse_crashed", extra={"extra_fields": {"resume_id": resume_id}}
            )
            await session.rollback()
            await parser.fail(
                rid, "Something went wrong while parsing this file. Please re-upload it."
            )


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(get_settings().log_level)


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ping, parse_resume]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_TRIES
    job_timeout = 180
    max_jobs = 4  # gentle on the free-tier LLM rate limit
