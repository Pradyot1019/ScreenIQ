"""Phase 2 integration tests: jobs, rubric, status machine, roles, AI drafting."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.llm.provider import get_llm_provider
from app.models import Job, LLMCall, Role
from tests.factories import JD_TEXT, add_member, create_job, signup, valid_rubric
from tests.fakes import FakeLLMProvider, fixture_text

# ---- create / read --------------------------------------------------------------------


async def test_create_job_is_201_draft_with_location(api: AsyncClient) -> None:
    owner = await signup(api, "owner@jobs.example")
    r = await api.post(
        "/api/v1/jobs",
        json={"title": "  Backend Engineer ", "description": JD_TEXT, "location": "Bengaluru"},
        headers=owner.headers,
    )
    assert r.status_code == 201
    job = r.json()
    assert r.headers["Location"] == f"/api/v1/jobs/{job['id']}"
    assert job["title"] == "Backend Engineer"
    assert job["status"] == "draft"
    assert job["employment_type"] == "full_time"
    assert job["criteria"] == []
    assert job["slug"].startswith("backend-engineer-")
    assert job["created_by"] == str(decode_access_token(owner.access_token).sub)

    got = await api.get(f"/api/v1/jobs/{job['id']}", headers=owner.headers)
    assert got.status_code == 200 and got.json() == job


async def test_create_job_validation(api: AsyncClient) -> None:
    owner = await signup(api, "v@jobs.example")
    for body in (
        {"title": "X", "description": "too short"},
        {"title": "", "description": JD_TEXT},
        {"title": "X", "description": JD_TEXT, "employment_type": "gig"},
    ):
        r = await api.post("/api/v1/jobs", json=body, headers=owner.headers)
        assert r.status_code == 422, body


async def test_unknown_job_is_404(api: AsyncClient) -> None:
    owner = await signup(api, "404@jobs.example")
    r = await api.get(f"/api/v1/jobs/{uuid.uuid4()}", headers=owner.headers)
    assert r.status_code == 404
    assert (await api.get("/api/v1/jobs/not-a-uuid", headers=owner.headers)).status_code == 422


# ---- list + cursor pagination ---------------------------------------------------------


async def _all_pages(api: AsyncClient, headers: dict[str, str]) -> tuple[list[str], int]:
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        r = await api.get("/api/v1/jobs", params=params, headers=headers)
        assert r.status_code == 200
        body = r.json()
        seen += [j["id"] for j in body["items"]]
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            return seen, pages


async def test_list_paginates_newest_first(api: AsyncClient, db_session: AsyncSession) -> None:
    owner = await signup(api, "list@jobs.example")
    created = [(await create_job(api, owner.headers, title=f"Job {i}"))["id"] for i in range(5)]
    # Each test runs in ONE transaction, and Postgres now() is the transaction's start
    # time, so all 5 jobs got the same created_at. Spread them out to test ordering.
    for i, job_id in enumerate(created):
        await db_session.execute(
            update(Job)
            .where(Job.id == uuid.UUID(job_id))
            .values(created_at=datetime.now(UTC) - timedelta(minutes=10 - i))
        )

    seen, pages = await _all_pages(api, owner.headers)
    assert pages == 3  # 2 + 2 + 1
    assert seen == list(reversed(created))  # newest first, no duplicates, none missing

    r = await api.get("/api/v1/jobs", params={"status": "open"}, headers=owner.headers)
    assert r.json() == {"items": [], "next_cursor": None}


async def test_list_pages_correctly_when_timestamps_tie(api: AsyncClient) -> None:
    # Same created_at for all 5 (see above): the id tie-breaker in the cursor must still
    # give every job exactly once. Without it, a page boundary inside the tie would
    # skip or repeat rows.
    owner = await signup(api, "tie@jobs.example")
    created = {(await create_job(api, owner.headers, title=f"Job {i}"))["id"] for i in range(5)}
    seen, pages = await _all_pages(api, owner.headers)
    assert pages == 3
    assert len(seen) == len(set(seen)) == 5
    assert set(seen) == created


async def test_bad_cursor_and_limit_are_422(api: AsyncClient) -> None:
    owner = await signup(api, "cursor@jobs.example")
    r = await api.get("/api/v1/jobs", params={"cursor": "garbage!"}, headers=owner.headers)
    assert r.status_code == 422 and r.json()["type"].endswith("invalid-cursor")
    r = await api.get("/api/v1/jobs", params={"limit": 1000}, headers=owner.headers)
    assert r.status_code == 422


# ---- update / delete ------------------------------------------------------------------


async def test_patch_changes_only_sent_fields(api: AsyncClient) -> None:
    owner = await signup(api, "patch@jobs.example")
    job = await create_job(api, owner.headers, location="Pune", department="Eng")
    r = await api.patch(
        f"/api/v1/jobs/{job['id']}",
        json={"title": "Senior Backend Engineer", "location": None},
        headers=owner.headers,
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["title"] == "Senior Backend Engineer"
    assert updated["location"] is None  # explicitly cleared
    assert updated["department"] == "Eng"  # not sent, so unchanged
    assert updated["description"] == job["description"]


async def test_patch_rejects_status_and_null_title(api: AsyncClient) -> None:
    owner = await signup(api, "patch2@jobs.example")
    job = await create_job(api, owner.headers)
    for body in ({"status": "open"}, {"title": None}):
        r = await api.patch(f"/api/v1/jobs/{job['id']}", json=body, headers=owner.headers)
        assert r.status_code == 422, body


async def test_delete_is_204_then_404(api: AsyncClient) -> None:
    owner = await signup(api, "del@jobs.example")
    job = await create_job(api, owner.headers)
    await api.put(f"/api/v1/jobs/{job['id']}/rubric", json=valid_rubric(), headers=owner.headers)
    r = await api.delete(f"/api/v1/jobs/{job['id']}", headers=owner.headers)
    assert r.status_code == 204 and r.content == b""
    assert (await api.get(f"/api/v1/jobs/{job['id']}", headers=owner.headers)).status_code == 404


# ---- rubric ---------------------------------------------------------------------------


async def test_put_rubric_replaces_whole_rubric_in_order(api: AsyncClient) -> None:
    owner = await signup(api, "rubric@jobs.example")
    job = await create_job(api, owner.headers)
    url = f"/api/v1/jobs/{job['id']}/rubric"

    r = await api.put(url, json=valid_rubric(), headers=owner.headers)
    assert r.status_code == 200
    names = [c["name"] for c in r.json()["criteria"]]
    assert names == ["Python", "PostgreSQL", "3+ years backend"]

    smaller = {"criteria": [{"name": "Go", "type": "skill", "weight": 100}]}
    r = await api.put(url, json=smaller, headers=owner.headers)
    assert [c["name"] for c in r.json()["criteria"]] == ["Go"]  # old rows are gone

    # Idempotent: same body again, same result.
    again = await api.put(url, json=smaller, headers=owner.headers)
    assert [c["name"] for c in again.json()["criteria"]] == ["Go"]


async def test_put_rubric_weights_must_total_100(api: AsyncClient) -> None:
    owner = await signup(api, "w@jobs.example")
    job = await create_job(api, owner.headers)
    rubric = valid_rubric()
    rubric["criteria"][0]["weight"] = 49  # type: ignore[index]
    r = await api.put(f"/api/v1/jobs/{job['id']}/rubric", json=rubric, headers=owner.headers)
    assert r.status_code == 422
    assert "add up to 100 (they add up to 99)" in r.text


async def test_put_rubric_rejects_duplicates_and_empty(api: AsyncClient) -> None:
    owner = await signup(api, "dupe@jobs.example")
    job = await create_job(api, owner.headers)
    url = f"/api/v1/jobs/{job['id']}/rubric"
    dupes = {
        "criteria": [
            {"name": "Python", "type": "skill", "weight": 50},
            {"name": "python", "type": "skill", "weight": 50},
        ]
    }
    assert (await api.put(url, json=dupes, headers=owner.headers)).status_code == 422
    assert (await api.put(url, json={"criteria": []}, headers=owner.headers)).status_code == 422


# ---- status machine -------------------------------------------------------------------


async def test_publish_and_close_lifecycle(api: AsyncClient) -> None:
    owner = await signup(api, "life@jobs.example")
    job = await create_job(api, owner.headers)
    base = f"/api/v1/jobs/{job['id']}"

    r = await api.post(f"{base}/publish", headers=owner.headers)
    assert r.status_code == 409  # no rubric yet
    assert "rubric" in r.json()["detail"]

    r = await api.post(f"{base}/close", headers=owner.headers)
    assert r.status_code == 409  # can't close a draft

    await api.put(f"{base}/rubric", json=valid_rubric(), headers=owner.headers)
    r = await api.post(f"{base}/publish", headers=owner.headers)
    assert r.status_code == 200 and r.json()["status"] == "open"
    r = await api.post(f"{base}/publish", headers=owner.headers)
    assert r.status_code == 200 and r.json()["status"] == "open"  # repeat = no-op

    r = await api.post(f"{base}/close", headers=owner.headers)
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert (await api.post(f"{base}/publish", headers=owner.headers)).status_code == 409
    r = await api.put(f"{base}/rubric", json=valid_rubric(), headers=owner.headers)
    assert r.status_code == 409  # closed jobs' rubrics are frozen


# ---- AI rubric draft (fake LLM) -------------------------------------------------------


async def test_generate_rubric_returns_draft_and_saves_nothing(
    api: AsyncClient, app: FastAPI, db_session: AsyncSession
) -> None:
    fake = FakeLLMProvider([fixture_text("llm/jd_parse_v1/backend_engineer.json")])
    app.dependency_overrides[get_llm_provider] = lambda: fake
    owner = await signup(api, "ai@jobs.example")
    job = await create_job(api, owner.headers)

    r = await api.post(f"/api/v1/jobs/{job['id']}/rubric:generate", headers=owner.headers)

    assert r.status_code == 200
    body = r.json()
    assert body["prompt_version"] == "jd_parse_v1"
    assert len(body["criteria"]) == 8
    assert sum(c["weight"] for c in body["criteria"]) == 100
    assert JD_TEXT in fake.calls[0].user  # defaults to the job's own description

    # A draft is only a suggestion: the job's rubric is untouched...
    saved = await api.get(f"/api/v1/jobs/{job['id']}", headers=owner.headers)
    assert saved.json()["criteria"] == []
    # ...but the LLM call was recorded for cost tracking.
    calls = await db_session.scalar(select(func.count()).select_from(LLMCall))
    assert calls == 1

    # The draft is directly saveable with PUT.
    r = await api.put(
        f"/api/v1/jobs/{job['id']}/rubric",
        json={"criteria": body["criteria"]},
        headers=owner.headers,
    )
    assert r.status_code == 200


async def test_generate_rubric_with_custom_jd(api: AsyncClient, app: FastAPI) -> None:
    fake = FakeLLMProvider([fixture_text("llm/jd_parse_v1/backend_engineer.json")])
    app.dependency_overrides[get_llm_provider] = lambda: fake
    owner = await signup(api, "ai2@jobs.example")
    job = await create_job(api, owner.headers)
    custom = "Data engineer with Spark, Airflow and 2+ years building batch pipelines in Python."

    url = f"/api/v1/jobs/{job['id']}/rubric:generate"
    r = await api.post(url, json={"jd_text": custom}, headers=owner.headers)
    assert r.status_code == 200
    assert custom in fake.calls[0].user
    r = await api.post(url, json={"jd_text": "short"}, headers=owner.headers)
    assert r.status_code == 422


async def test_generate_rubric_without_api_key_is_503(api: AsyncClient) -> None:
    # No fake installed and GEMINI_API_KEY is blank in tests -> feature unavailable.
    owner = await signup(api, "nokey@jobs.example")
    job = await create_job(api, owner.headers)
    r = await api.post(f"/api/v1/jobs/{job['id']}/rubric:generate", headers=owner.headers)
    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.json()["detail"]


# ---- roles ----------------------------------------------------------------------------


async def test_viewer_can_read_but_not_write(
    api: AsyncClient, app: FastAPI, db_session: AsyncSession
) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider([])
    owner = await signup(api, "boss@jobs.example")
    org_id = decode_access_token(owner.access_token).org
    job = await create_job(api, owner.headers)
    viewer = await add_member(db_session, org_id, Role.VIEWER)
    recruiter = await add_member(db_session, org_id, Role.RECRUITER)
    base = f"/api/v1/jobs/{job['id']}"

    assert (await api.get("/api/v1/jobs", headers=viewer)).status_code == 200
    assert (await api.get(base, headers=viewer)).status_code == 200

    writes = [
        ("POST", "/api/v1/jobs", {"title": "X", "description": JD_TEXT}),
        ("PATCH", base, {"title": "Hacked"}),
        ("PUT", f"{base}/rubric", valid_rubric()),
        ("POST", f"{base}/rubric:generate", None),
        ("POST", f"{base}/publish", None),
        ("POST", f"{base}/close", None),
        ("DELETE", base, None),
    ]
    for method, url, body in writes:
        r = await api.request(method, url, json=body, headers=viewer)
        assert r.status_code == 403, (method, url)

    # Recruiters can write.
    r = await api.patch(base, json={"title": "Edited by recruiter"}, headers=recruiter)
    assert r.status_code == 200
