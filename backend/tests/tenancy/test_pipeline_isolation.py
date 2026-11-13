"""Tenancy for Phase 5 endpoints: another org gets 404 and changes nothing."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import signup
from tests.scenarios import World


async def test_cross_org_pipeline_endpoints_are_404(
    api: AsyncClient, db_session: AsyncSession, world: World
) -> None:
    mallory = await signup(api, f"mallory-{uuid.uuid4().hex[:6]}@b.example", org_name="Org B")
    app_url = f"/api/v1/applications/{world.application_id}"
    calls = [
        ("PATCH", app_url, {"stage": "rejected"}),
        ("GET", f"{app_url}/notes", None),
        ("POST", f"{app_url}/notes", {"body": "pwned"}),
        ("GET", f"{app_url}/resume", None),
        (
            "GET",
            f"/api/v1/jobs/{world.job_id}/applications:compare?ids={world.application_id},{uuid.uuid4()}",
            None,
        ),
    ]
    for method, url, body in calls:
        r = await api.request(method, url, json=body, headers=mallory.headers)
        assert r.status_code == 404, (method, url)
        assert "Priya" not in r.text

    # Nothing changed for the real owner.
    detail = (await api.get(app_url, headers=world.headers)).json()
    assert detail["stage"] == "applied" and detail["history"] == []
    assert (await api.get(f"{app_url}/notes", headers=world.headers)).json() == []
