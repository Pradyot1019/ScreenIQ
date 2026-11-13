"""Phase 3: upload API, worker-side parsing, dedupe, retries, batch progress."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from arq import Retry
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.llm.provider import LLMBusyError
from app.models import Application, Candidate, LLMCall, LLMPurpose, Role
from app.services.intake import ResumeParser, TransientParseError
from app.storage.s3 import get_storage
from app.workers import arq_worker
from app.workers.queue import get_queue
from tests.factories import add_member, create_job, signup
from tests.fakes import (
    FakeLLMProvider,
    FakeQueue,
    InMemoryStorage,
    fixture_text,
    make_docx,
    make_pdf,
)

PRIYA_PDF = make_pdf(fixture_text("resumes/priya_sharma.txt"))
PRIYA_JSON = fixture_text("llm/resume_parse_v1/priya_sharma.json")


@pytest.fixture
def storage(app: FastAPI) -> InMemoryStorage:
    s = InMemoryStorage()
    app.dependency_overrides[get_storage] = lambda: s
    return s


@pytest.fixture
def queue(app: FastAPI) -> FakeQueue:
    q = FakeQueue()
    app.dependency_overrides[get_queue] = lambda: q
    return q


def _files(*items: tuple[str, bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (name, data, "application/octet-stream")) for name, data in items]


async def _upload(api: AsyncClient, headers: dict[str, str], job_id: str, *files: Any) -> Any:
    r = await api.post(f"/api/v1/jobs/{job_id}/resumes", files=_files(*files), headers=headers)
    assert r.status_code == 202, r.text
    return r


async def _count(db: AsyncSession, model: Any) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


# ---- upload API -----------------------------------------------------------------------


async def test_upload_stores_valid_files_and_reports_bad_ones(
    api: AsyncClient, storage: InMemoryStorage, queue: FakeQueue
) -> None:
    owner = await signup(api, "up@intake.example")
    org_id = decode_access_token(owner.access_token).org
    job = await create_job(api, owner.headers)
    docx_bytes = make_docx(
        ["Rahul Verma", "Data engineer, 4 years of Spark and Airflow in production."]
    )

    r = await _upload(
        api,
        owner.headers,
        job["id"],
        ("priya.pdf", PRIYA_PDF),
        ("rahul.docx", docx_bytes),
        ("virus.pdf", b"MZ not a pdf at all"),
    )

    batch = r.json()
    assert r.headers["Location"] == f"/api/v1/batches/{batch['id']}"
    assert (batch["total"], batch["failed"], batch["status"]) == (3, 1, "processing")
    by_name = {f["filename"]: f for f in batch["files"]}
    assert by_name["priya.pdf"]["status"] == "queued"
    assert by_name["virus.pdf"]["status"] == "failed"
    assert "Only PDF and DOCX" in by_name["virus.pdf"]["error"]

    # Valid files are in storage under the org's prefix; the bad one isn't stored.
    assert len(storage.objects) == 2
    assert all(k.startswith(f"orgs/{org_id}/resumes/") for k in storage.objects)
    # One parse job per valid file, with an idempotent job id.
    assert sorted(job_id for _, _, job_id in queue.jobs) == sorted(
        f"parse:{f['resume_id']}" for f in batch["files"] if f["status"] == "queued"
    )

    polled = await api.get(f"/api/v1/batches/{batch['id']}", headers=owner.headers)
    assert polled.status_code == 200 and polled.json()["total"] == 3


async def test_upload_limits(api: AsyncClient, storage: InMemoryStorage, queue: FakeQueue) -> None:
    owner = await signup(api, "limits@intake.example")
    job = await create_job(api, owner.headers)
    url = f"/api/v1/jobs/{job['id']}/resumes"
    assert (await api.post(url, headers=owner.headers)).status_code == 422  # no files
    too_many = _files(*[(f"{i}.pdf", PRIYA_PDF) for i in range(51)])
    r = await api.post(url, files=too_many, headers=owner.headers)
    assert r.status_code == 422 and "between 1 and 50" in r.json()["detail"]
    assert storage.objects == {} and queue.jobs == []


async def test_upload_to_closed_job_is_409_and_viewer_is_403(
    api: AsyncClient, db_session: AsyncSession, storage: InMemoryStorage, queue: FakeQueue
) -> None:
    owner = await signup(api, "closed@intake.example")
    job = await create_job(api, owner.headers)
    rubric = {"criteria": [{"name": "Python", "type": "skill", "weight": 100}]}
    await api.put(f"/api/v1/jobs/{job['id']}/rubric", json=rubric, headers=owner.headers)
    await api.post(f"/api/v1/jobs/{job['id']}/publish", headers=owner.headers)
    viewer = await add_member(db_session, decode_access_token(owner.access_token).org, Role.VIEWER)
    url = f"/api/v1/jobs/{job['id']}/resumes"

    r = await api.post(url, files=_files(("a.pdf", PRIYA_PDF)), headers=viewer)
    assert r.status_code == 403
    await api.post(f"/api/v1/jobs/{job['id']}/close", headers=owner.headers)
    r = await api.post(url, files=_files(("a.pdf", PRIYA_PDF)), headers=owner.headers)
    assert r.status_code == 409


# ---- worker-side parsing --------------------------------------------------------------


async def _uploaded(
    api: AsyncClient,
    storage: InMemoryStorage,
    *files: tuple[str, bytes],
    email: str = "w@i.example",
) -> tuple[dict[str, str], dict[str, Any], list[uuid.UUID]]:
    owner = await signup(api, email)
    job = await create_job(api, owner.headers)
    batch = (await _upload(api, owner.headers, job["id"], *files)).json()
    return owner.headers, batch, [uuid.UUID(f["resume_id"]) for f in batch["files"]]


async def test_parse_creates_candidate_application_and_completes_batch(
    api: AsyncClient, db_session: AsyncSession, storage: InMemoryStorage, queue: FakeQueue
) -> None:
    headers, batch, [rid] = await _uploaded(api, storage, ("priya.pdf", PRIYA_PDF))
    fake = FakeLLMProvider([PRIYA_JSON])

    await ResumeParser(db_session, storage, fake).run(rid)

    assert "<resume>" in fake.calls[0].user and "Priya Sharma" in fake.calls[0].user
    done = (await api.get(f"/api/v1/batches/{batch['id']}", headers=headers)).json()
    assert (done["status"], done["processed"], done["failed"]) == ("done", 1, 0)
    assert done["files"][0]["status"] == "parsed"
    assert done["files"][0]["candidate_name"] == "Priya Sharma"

    candidate = (await db_session.execute(select(Candidate))).scalar_one()
    assert candidate.email == "priya.sharma@example.com"
    assert str(candidate.total_experience_years) == "6.3"
    assert "FastAPI" in candidate.parsed["skills"]
    assert await _count(db_session, Application) == 1
    call = (await db_session.execute(select(LLMCall))).scalar_one()
    assert (call.purpose, call.prompt_version) == (LLMPurpose.RESUME_PARSE, "resume_parse_v1")

    # Idempotent: a duplicate queue delivery does nothing (and calls no LLM).
    await ResumeParser(db_session, storage, FakeLLMProvider([])).run(rid)


async def test_same_email_reuses_candidate_and_same_file_skips_the_llm(
    api: AsyncClient, db_session: AsyncSession, storage: InMemoryStorage, queue: FakeQueue
) -> None:
    other_file = make_pdf(fixture_text("resumes/priya_sharma.txt") + "\nUpdated 2026")
    _, batch, _ = await _uploaded(
        api,
        storage,
        ("v1.pdf", PRIYA_PDF),
        ("v2.pdf", other_file),  # different bytes, same email inside
        ("v1-again.pdf", PRIYA_PDF),  # identical bytes
        email="dedupe@i.example",
    )
    ids = {f["filename"]: uuid.UUID(f["resume_id"]) for f in batch["files"]}
    first, second, third = ids["v1.pdf"], ids["v2.pdf"], ids["v1-again.pdf"]
    await ResumeParser(db_session, storage, FakeLLMProvider([PRIYA_JSON])).run(first)
    await ResumeParser(db_session, storage, FakeLLMProvider([PRIYA_JSON])).run(second)
    no_llm = FakeLLMProvider([])  # would raise if called
    await ResumeParser(db_session, storage, no_llm).run(third)

    assert await _count(db_session, Candidate) == 1  # FR-24: one person, one candidate
    assert await _count(db_session, Application) == 1  # one application per job
    assert no_llm.calls == []  # hash dedupe saved an LLM call
    assert await _count(db_session, LLMCall) == 2


async def test_unreadable_file_fails_with_reason(
    api: AsyncClient, db_session: AsyncSession, storage: InMemoryStorage, queue: FakeQueue
) -> None:
    headers, batch, [rid] = await _uploaded(
        api, storage, ("scan.pdf", make_pdf("")), email="scan@i.example"
    )
    await ResumeParser(db_session, storage, FakeLLMProvider([])).run(rid)
    done = (await api.get(f"/api/v1/batches/{batch['id']}", headers=headers)).json()
    assert (done["status"], done["failed"]) == ("done", 1)
    assert "Scanned PDFs" in done["files"][0]["error"]


async def test_llm_busy_is_retried_with_backoff_then_fails_on_last_try(
    api: AsyncClient,
    db_session: AsyncSession,
    storage: InMemoryStorage,
    queue: FakeQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, batch, [rid] = await _uploaded(
        api, storage, ("p.pdf", PRIYA_PDF), email="busy@i.example"
    )
    with pytest.raises(TransientParseError):
        await ResumeParser(db_session, storage, FakeLLMProvider([LLMBusyError("gemini_429")])).run(
            rid
        )

    # Drive the real ARQ task with the test DB, storage and an always-busy LLM.
    @asynccontextmanager
    async def test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    monkeypatch.setattr(arq_worker, "SessionLocal", test_session)
    monkeypatch.setattr(arq_worker, "get_storage", lambda: storage)
    monkeypatch.setattr(
        arq_worker, "get_llm_provider", lambda: FakeLLMProvider([LLMBusyError("gemini_503")])
    )

    with pytest.raises(Retry) as retry:
        await arq_worker.parse_resume({"job_try": 2}, str(rid))
    assert retry.value.defer_score == 30_000  # 15s * 2^(2-1), in ms

    await arq_worker.parse_resume({"job_try": 3}, str(rid))  # last try: give up cleanly
    done = (await api.get(f"/api/v1/batches/{batch['id']}", headers=headers)).json()
    assert done["files"][0]["status"] == "failed"
    assert "busy" in done["files"][0]["error"]
    assert done["status"] == "done"


async def test_unexpected_crash_marks_file_failed_instead_of_hanging(
    api: AsyncClient,
    db_session: AsyncSession,
    storage: InMemoryStorage,
    queue: FakeQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, batch, [rid] = await _uploaded(
        api, storage, ("p.pdf", PRIYA_PDF), email="crash@i.example"
    )

    async def boom(key: str) -> bytes:
        raise RuntimeError("disk on fire")

    @asynccontextmanager
    async def test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    monkeypatch.setattr(storage, "get", boom)
    monkeypatch.setattr(arq_worker, "SessionLocal", test_session)
    monkeypatch.setattr(arq_worker, "get_storage", lambda: storage)
    monkeypatch.setattr(arq_worker, "get_llm_provider", lambda: FakeLLMProvider([]))

    await arq_worker.parse_resume({"job_try": 1}, str(rid))  # must not raise

    done = (await api.get(f"/api/v1/batches/{batch['id']}", headers=headers)).json()
    assert done["status"] == "done"
    assert done["files"][0]["status"] == "failed"
    assert "disk on fire" not in done["files"][0]["error"]  # internals aren't shown to users
