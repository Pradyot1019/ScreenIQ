"""Tenancy for intake: another org can't upload to, or read the progress of, your jobs."""

from fastapi import FastAPI
from httpx import AsyncClient

from app.storage.s3 import get_storage
from app.workers.queue import get_queue
from tests.factories import create_job, signup
from tests.fakes import FakeQueue, InMemoryStorage, fixture_text, make_pdf

PDF = make_pdf(fixture_text("resumes/priya_sharma.txt"))


async def test_cross_org_upload_and_batch_are_404(api: AsyncClient, app: FastAPI) -> None:
    storage, queue = InMemoryStorage(), FakeQueue()
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_queue] = lambda: queue
    alice = await signup(api, "alice@a.example", org_name="Org A")
    bob = await signup(api, "bob@b.example", org_name="Org B")
    job = await create_job(api, alice.headers)
    files = [("files", ("cv.pdf", PDF, "application/pdf"))]

    r = await api.post(f"/api/v1/jobs/{job['id']}/resumes", files=files, headers=bob.headers)
    assert r.status_code == 404
    assert storage.objects == {} and queue.jobs == []  # nothing stored or queued

    r = await api.post(f"/api/v1/jobs/{job['id']}/resumes", files=files, headers=alice.headers)
    batch_id = r.json()["id"]
    r = await api.get(f"/api/v1/batches/{batch_id}", headers=bob.headers)
    assert r.status_code == 404
    assert "cv.pdf" not in r.text
