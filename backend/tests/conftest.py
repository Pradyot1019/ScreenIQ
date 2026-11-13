"""Shared fixtures.

- `client`: the app with no database; for tests that don't need one (health, errors).
- `db_session`: a session on a real Postgres test database (`<dbname>_test`). The DB is
  dropped and rebuilt with `alembic upgrade head` once per test run, so the tests also
  prove the migrations work. Each test runs inside a transaction that is rolled back at
  the end, so tests never see each other's data and need no cleanup.
- `api`: an HTTP client for the app, wired to `db_session`.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings

# Point the whole test run at a separate database BEFORE the app (and its engine) loads.
_dev_url = make_url(os.environ.get("DATABASE_URL") or Settings().database_url)
TEST_DATABASE_URL = _dev_url.set(database=f"{_dev_url.database}_test").render_as_string(
    hide_password=False
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["APP_ENV"] = "test"
# Tests must never call a real LLM (cost, flakiness, data leaving the machine), even if
# a developer's .env has a real key. Tests that need an LLM install FakeLLMProvider.
os.environ["GEMINI_API_KEY"] = ""

import asyncpg  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402

if TYPE_CHECKING:
    from tests.scenarios import World

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _recreate_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    assert url.database and url.database.endswith("_test"), "refusing to drop a non-test DB"
    conn = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database="postgres",
    )
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def migrated_db() -> str:
    asyncio.run(_recreate_test_database())
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def db_session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    async with engine.connect() as conn:
        outer = await conn.begin()
        # Code under test calls session.commit(); in this mode that only releases a
        # SAVEPOINT inside `outer`, which we roll back after the test.
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    """The app wired to the test DB. Tests can add more overrides, e.g. a fake LLM:
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider([...])"""
    application = create_app()

    async def _test_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db] = _test_db
    return application


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def world(app: FastAPI, api: AsyncClient, db_session: AsyncSession) -> "World":
    """An org with a job (rubric saved) and Priya's parsed, not-yet-screened application."""
    from tests.scenarios import World, build_world

    result: World = await build_world(app, api, db_session)
    return result
