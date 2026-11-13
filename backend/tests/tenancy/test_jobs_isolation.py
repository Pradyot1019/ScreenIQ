"""Tenancy suite for jobs: every job endpoint, called by another org, must be a 404
and must not change anything."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.llm.provider import get_llm_provider
from tests.factories import JD_TEXT, create_job, signup, valid_rubric
from tests.fakes import FakeLLMProvider

# (method, path template, body). {id} = a job that belongs to Org A.
JOB_ENDPOINTS = [
    ("GET", "/api/v1/jobs/{id}", None),
    ("PATCH", "/api/v1/jobs/{id}", {"title": "Pwned"}),
    ("DELETE", "/api/v1/jobs/{id}", None),
    ("PUT", "/api/v1/jobs/{id}/rubric", valid_rubric()),
    ("POST", "/api/v1/jobs/{id}/rubric:generate", None),
    ("POST", "/api/v1/jobs/{id}/publish", None),
    ("POST", "/api/v1/jobs/{id}/close", None),
]


@pytest.mark.parametrize(
    ("method", "path", "body"), JOB_ENDPOINTS, ids=[f"{m} {p}" for m, p, _ in JOB_ENDPOINTS]
)
async def test_other_orgs_job_is_404_and_untouched(
    api: AsyncClient, app: FastAPI, method: str, path: str, body: dict[str, object] | None
) -> None:
    fake = FakeLLMProvider([])  # must never be called for a job we can't see
    app.dependency_overrides[get_llm_provider] = lambda: fake
    alice = await signup(api, "alice@a.example", org_name="Org A")
    bob = await signup(api, "bob@b.example", org_name="Org B")
    job = await create_job(api, alice.headers, title="Org A secret role")

    r = await api.request(method, path.format(id=job["id"]), json=body, headers=bob.headers)

    assert r.status_code == 404
    assert "Org A secret role" not in r.text
    assert fake.calls == []
    after = await api.get(f"/api/v1/jobs/{job['id']}", headers=alice.headers)
    assert after.status_code == 200
    assert after.json() == job  # unchanged: same title, status, rubric


async def test_job_list_only_shows_own_org(api: AsyncClient) -> None:
    alice = await signup(api, "alice2@a.example", org_name="Org A")
    bob = await signup(api, "bob2@b.example", org_name="Org B")
    await create_job(api, alice.headers, title="A1")
    await create_job(api, bob.headers, title="B1", description=JD_TEXT)

    a_titles = [
        j["title"] for j in (await api.get("/api/v1/jobs", headers=alice.headers)).json()["items"]
    ]
    b_titles = [
        j["title"] for j in (await api.get("/api/v1/jobs", headers=bob.headers)).json()["items"]
    ]
    assert a_titles == ["A1"]
    assert b_titles == ["B1"]
