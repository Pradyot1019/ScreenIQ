"""Phase 5: stage moves + history, notes, resume view with highlights, compare."""

import json
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role
from app.services.intake import ResumeParser
from tests.factories import add_member
from tests.fakes import FakeLLMProvider, fixture_text, make_pdf
from tests.scenarios import PRIYA_SCREEN, World, _screen

KARAN_TEXT = (
    "Karan Mehta\nBackend Developer | karan.mehta@example.com\n"
    "Software Engineer, PayLoop (2020 - Present)\n- Built payment APIs in Go and Python\n"
    "SKILLS: Go, Python, PostgreSQL, Kubernetes"
)
KARAN_PARSE = json.dumps(
    {"name": "Karan Mehta", "email": "karan.mehta@example.com", "skills": ["Go", "Python"]}
)


async def test_stage_moves_are_logged_with_who_did_them(
    api: AsyncClient, db_session: AsyncSession, world: World
) -> None:
    await _screen(api, db_session, world, PRIYA_SCREEN)  # AI: applied -> screened
    url = f"/api/v1/applications/{world.application_id}"

    r = await api.patch(url, json={"stage": "shortlisted"}, headers=world.headers)
    assert r.status_code == 200 and r.json()["stage"] == "shortlisted"
    await api.patch(url, json={"stage": "shortlisted"}, headers=world.headers)  # no-op
    r = await api.patch(url, json={"stage": "rejected"}, headers=world.headers)
    assert r.json()["stage"] == "rejected"  # a person may reject; the AI never does

    history = (await api.get(url, headers=world.headers)).json()["history"]
    assert [(h["from_stage"], h["to_stage"], h["actor_name"]) for h in history] == [
        ("applied", "screened", None),  # None = the AI screening
        ("screened", "shortlisted", "Test User"),
        ("shortlisted", "rejected", "Test User"),
    ]
    assert (await api.patch(url, json={"stage": "fired"}, headers=world.headers)).status_code == 422


async def test_viewer_can_comment_but_not_move(
    api: AsyncClient, db_session: AsyncSession, world: World
) -> None:
    viewer = await add_member(db_session, world.org_id, Role.VIEWER)
    url = f"/api/v1/applications/{world.application_id}"
    r = await api.patch(url, json={"stage": "shortlisted"}, headers=viewer)
    assert r.status_code == 403

    r = await api.post(
        f"{url}/notes", json={"body": "  Strong API work, ask about scale.  "}, headers=viewer
    )
    assert r.status_code == 201
    assert r.json()["body"] == "Strong API work, ask about scale."
    assert r.json()["author_name"] == "Test viewer"
    await api.post(f"{url}/notes", json={"body": "Agreed."}, headers=world.headers)
    notes = (await api.get(f"{url}/notes", headers=world.headers)).json()
    assert [n["body"] for n in notes] == ["Strong API work, ask about scale.", "Agreed."]
    r = await api.post(f"{url}/notes", json={"body": "   "}, headers=world.headers)
    assert r.status_code == 422


async def test_resume_view_has_signed_url_and_highlights(
    api: AsyncClient, db_session: AsyncSession, world: World
) -> None:
    await _screen(api, db_session, world, PRIYA_SCREEN)
    r = await api.get(f"/api/v1/applications/{world.application_id}/resume", headers=world.headers)
    assert r.status_code == 200
    view = r.json()
    assert view["filename"] == "priya.pdf" and view["mime_type"] == "application/pdf"
    assert view["url"].startswith(f"http://storage.test/orgs/{world.org_id}/resumes/")
    assert "expires=300" in view["url"] and view["url_expires_in"] == 300

    # 4 verified quotes in the recorded screening; each is located in the resume text.
    text = view["text"]
    spans = [(h["criterion"], text[h["start"] : h["end"]]) for h in view["highlights"]]
    assert len(spans) == 4
    assert (
        "PostgreSQL",
        "Designed PostgreSQL schemas and cut slow-query time by 60% with indexing",
    ) in [(c, " ".join(s.split())) for c, s in spans]
    assert all("Google" not in s for _, s in spans)  # the made-up quote is never highlighted


async def test_compare_two_candidates(
    api: AsyncClient, db_session: AsyncSession, world: World
) -> None:
    await _screen(api, db_session, world, PRIYA_SCREEN)
    files = [("files", ("karan.pdf", make_pdf(KARAN_TEXT), "application/pdf"))]
    batch = (
        await api.post(f"/api/v1/jobs/{world.job_id}/resumes", files=files, headers=world.headers)
    ).json()
    karan = await ResumeParser(db_session, world.storage, FakeLLMProvider([KARAN_PARSE])).run(
        uuid.UUID(batch["files"][0]["resume_id"])
    )
    url = f"/api/v1/jobs/{world.job_id}/applications:compare"

    r = await api.get(url, params={"ids": f"{world.application_id},{karan}"}, headers=world.headers)
    assert r.status_code == 200
    body = r.json()
    assert body["criteria"] == ["Python", "PostgreSQL", "3+ years backend"]
    priya, karan_col = body["candidates"]
    assert priya["name"] == "Priya Sharma" and priya["scores"]["Python"] == 9
    assert priya["low_confidence"] == ["3+ years backend"]
    assert karan_col["name"] == "Karan Mehta" and karan_col["scores"] == {}  # not screened yet

    one = await api.get(url, params={"ids": str(world.application_id)}, headers=world.headers)
    assert one.status_code == 422
    bad = await api.get(url, params={"ids": "not-a-uuid,also-not"}, headers=world.headers)
    assert bad.status_code == 422
    other = await api.get(
        url, params={"ids": f"{world.application_id},{uuid.uuid4()}"}, headers=world.headers
    )
    assert other.status_code == 404


async def test_pdf_fixture_is_generated() -> None:
    assert fixture_text("resumes/priya_sharma.txt").startswith("Priya Sharma")
