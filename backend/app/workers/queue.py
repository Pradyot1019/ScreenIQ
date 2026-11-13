"""Enqueueing background jobs from the API (the ARQ client side)."""

from typing import Any, Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings


class Queue(Protocol):
    async def enqueue(self, function: str, *args: Any, job_id: str) -> None: ...


class ArqQueue:
    def __init__(self) -> None:
        self._pool: ArqRedis | None = None

    async def enqueue(self, function: str, *args: Any, job_id: str) -> None:
        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        # A fixed job_id makes enqueueing idempotent: ARQ ignores a second job with the
        # same id while the first is queued or running.
        await self._pool.enqueue_job(function, *args, _job_id=job_id)


_queue = ArqQueue()


def get_queue() -> Queue:
    """FastAPI dependency; tests override it with a fake that records calls."""
    return _queue
