"""ARQ worker entrypoint. Run with:  arq app.workers.arq_worker.WorkerSettings

Phase 0 only registers a `ping` task to prove the queue round-trips.
Parsing and screening tasks arrive in Phases 3–4.
"""

from typing import Any, ClassVar

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging


async def ping(ctx: dict[str, Any]) -> str:
    return "pong"


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(get_settings().log_level)


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ping]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3  # spec: 3 attempts with backoff
    job_timeout = 120
