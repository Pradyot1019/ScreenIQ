"""Tenancy for applications/screenings: another org gets 404 everywhere."""

import uuid

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.intake import ResumeParser
from app.storage.s3 import get_storage
from app.workers.queue import get_queue
from tests.factories import create_job, signup, valid_rubric
from tests.fakes import FakeLLMProvider, FakeQueue, InMemoryStorage, fixture_text, make_pdf


async def test_cross_org_application_endpoints_are_404(
    api: AsyncClient, app: FastAPI, db_session: AsyncSession
) -> None:
    storage, queue = InMemoryStorage(), FakeQueue()
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_queue] = lambda: queue
    alice = await signup(api, "alice@a.example", org_name="Org A")
    bob = await signup(api, "bob@b.example", org_name="Org B")
    job = await create_job(api, alice.headers)
    await api.put(f"/api/v1/jobs/{job['id']}/rubric", json=valid_rubric(), headers=alice.headers)
    files = [
        ("files", ("p.pdf", make_pdf(fixture_text("resumes/priya_sharma.txt")), "application/pdf"))
    ]
    batch = (
        await api.post(f"/api/v1/jobs/{job['id']}/resumes", files=files, headers=alice.headers)
    ).json()
    parse = FakeLLMProvider([fixture_text("llm/resume_parse_v1/priya_sharma.json")])
    app_id = await ResumeParser(db_session, storage, parse).run(
        uuid.UUID(batch["files"][0]["resume_id"])
    )
    queue.jobs.clear()

    for method, url in [
        ("GET", f"/api/v1/jobs/{job['id']}/applications"),
        ("GET", f"/api/v1/applications/{app_id}"),
        ("POST", f"/api/v1/applications/{app_id}/screenings"),
        ("POST", f"/api/v1/jobs/{job['id']}/screenings"),
    ]:
        r = await api.request(method, url, headers=bob.headers)
        assert r.status_code == 404, (method, url)
        assert "Priya" not in r.text
    assert queue.jobs == []  # nothing was queued on Org A's behalf
