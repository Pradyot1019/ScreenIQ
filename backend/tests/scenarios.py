"""Shared test scenario: an org with a job (rubric saved) and Priya's parsed application.

Used by the screening, pipeline and tenancy tests via the `world` fixture in conftest.py.
"""

import uuid
from dataclasses import dataclass, field

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.services.intake import ResumeParser
from app.services.screening import ScreeningRunner
from app.storage.s3 import get_storage
from app.workers.queue import get_queue
from tests.factories import create_job, signup, valid_rubric
from tests.fakes import FakeLLMProvider, FakeQueue, InMemoryStorage, fixture_text, make_pdf

PRIYA_PDF = make_pdf(fixture_text("resumes/priya_sharma.txt"))
PRIYA_PARSE = fixture_text("llm/resume_parse_v1/priya_sharma.json")
PRIYA_SCREEN = fixture_text("llm/screen_v1/priya_backend.json")
INFLATED = fixture_text("llm/screen_v1/injected_inflated.json")


@dataclass
class World:
    headers: dict[str, str]
    org_id: uuid.UUID
    job_id: str
    application_id: uuid.UUID
    queue: FakeQueue
    storage: InMemoryStorage = field(repr=False)


async def build_world(app: FastAPI, api: AsyncClient, db_session: AsyncSession) -> World:
    storage, queue = InMemoryStorage(), FakeQueue()
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_queue] = lambda: queue
    owner = await signup(api, f"screen-{uuid.uuid4().hex[:6]}@example.com")
    job = await create_job(api, owner.headers)
    await api.put(f"/api/v1/jobs/{job['id']}/rubric", json=valid_rubric(), headers=owner.headers)
    files = [("files", ("priya.pdf", PRIYA_PDF, "application/pdf"))]
    r = await api.post(f"/api/v1/jobs/{job['id']}/resumes", files=files, headers=owner.headers)
    rid = uuid.UUID(r.json()["files"][0]["resume_id"])
    app_id = await ResumeParser(db_session, storage, FakeLLMProvider([PRIYA_PARSE])).run(rid)
    assert app_id is not None
    queue.jobs.clear()
    return World(
        headers=owner.headers,
        org_id=decode_access_token(owner.access_token).org,
        job_id=job["id"],
        application_id=app_id,
        queue=queue,
        storage=storage,
    )


async def _screen(api: AsyncClient, db: AsyncSession, w: World, reply: str) -> FakeLLMProvider:
    """Request a screening through the API, then run it with a fake LLM reply."""
    r = await api.post(f"/api/v1/applications/{w.application_id}/screenings", headers=w.headers)
    assert r.status_code == 202, r.text
    fake = FakeLLMProvider([reply])
    await ScreeningRunner(db, fake).run(uuid.UUID(r.json()["id"]))
    return fake
