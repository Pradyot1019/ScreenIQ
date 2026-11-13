"""Liveness and readiness probes.

- /health  = "is the process alive?"  Never touches dependencies, so a slow DB
             doesn't make the orchestrator kill a healthy process.
- /ready   = "can I serve traffic?"   Checks Postgres and Redis. Returns 503 if
             either is down, so the load balancer routes around this instance.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok"]


class ReadyOut(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(status="ok")


async def _check_db(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    client: Redis = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()


@router.get("/ready", response_model=ReadyOut)
async def ready(response: Response, db: Annotated[AsyncSession, Depends(get_db)]) -> ReadyOut:
    checks = {"database": await _check_db(db), "redis": await _check_redis()}
    ok = all(checks.values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyOut(status="ready" if ok else "not_ready", checks=checks)
