"""Tenancy suite (spec FR-06, Section 14): one org must never see another org's data.

Rule: a cross-org request returns 404, never 403 and never the other org's data.
Every new tenant endpoint gets a test in this folder.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, decode_access_token
from app.models import Membership, Role
from app.repositories.memberships import MembershipRepository
from tests.factories import call_refresh, signup


async def _two_orgs(api: AsyncClient) -> tuple[dict[str, str], dict[str, str], str, str]:
    """Alice owns org A, Bob owns org B. Returns (alice headers, bob headers, A id, B id)."""
    alice = await signup(api, "alice@a.example", org_name="Org A")
    bob = await signup(api, "bob@b.example", org_name="Org B")
    org_a = (await api.get("/api/v1/org", headers=alice.headers)).json()["id"]
    org_b = (await api.get("/api/v1/org", headers=bob.headers)).json()["id"]
    return alice.headers, bob.headers, org_a, org_b


async def test_each_user_sees_only_their_own_org(api: AsyncClient) -> None:
    alice, bob, org_a, org_b = await _two_orgs(api)
    assert org_a != org_b
    assert (await api.get("/api/v1/org", headers=alice)).json()["name"] == "Org A"
    assert (await api.get("/api/v1/org", headers=bob)).json()["name"] == "Org B"

    me = (await api.get("/api/v1/me", headers=alice)).json()
    assert [m["org_id"] for m in me["memberships"]] == [org_a]


async def test_token_for_an_org_you_dont_belong_to_is_404(api: AsyncClient) -> None:
    alice, _, _, org_b = await _two_orgs(api)
    alice_id = decode_access_token(alice["Authorization"].removeprefix("Bearer ")).sub

    # Worst case: a validly signed token that names Org B (e.g. a bug elsewhere minted it).
    forged = create_access_token(alice_id, uuid.UUID(org_b))
    r = await api.get("/api/v1/org", headers={"Authorization": f"Bearer {forged}"})

    assert r.status_code == 404  # not 403: don't even confirm Org B exists
    assert "Org B" not in r.text


async def test_removed_member_loses_access_immediately(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    alice = await signup(api, "removed@a.example", org_name="Org A")
    claims = decode_access_token(alice.access_token)
    await db_session.execute(
        delete(Membership).where(Membership.user_id == claims.sub, Membership.org_id == claims.org)
    )

    # The access token is still cryptographically valid, but membership is re-checked.
    assert (await api.get("/api/v1/org", headers=alice.headers)).status_code == 404
    # And the refresh token can't mint new access to that org.
    assert (await call_refresh(api, alice.refresh_token)).status_code == 401


async def test_tenant_repository_never_reads_across_orgs(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    alice, bob, org_a, org_b = await _two_orgs(api)
    repo_a = MembershipRepository(db_session, uuid.UUID(org_a))
    repo_b = MembershipRepository(db_session, uuid.UUID(org_b))

    a_rows = await repo_a.list()
    b_rows = await repo_b.list()
    assert {m.org_id for m in a_rows} == {uuid.UUID(org_a)}
    assert {m.org_id for m in b_rows} == {uuid.UUID(org_b)}

    # Fetching B's row by its exact id through A's repository finds nothing.
    assert await repo_a.get(b_rows[0].id) is None
    assert await repo_a.get_for_user(b_rows[0].user_id) is None


async def test_tenant_repository_add_stamps_its_own_org(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    _, bob, org_a, org_b = await _two_orgs(api)
    bob_id = decode_access_token(bob["Authorization"].removeprefix("Bearer ")).sub

    # Caller tries to sneak a row into Org B through Org A's repository.
    m = Membership(user_id=bob_id, role=Role.VIEWER, org_id=uuid.UUID(org_b))
    saved = await MembershipRepository(db_session, uuid.UUID(org_a)).add(m)
    assert saved.org_id == uuid.UUID(org_a)
