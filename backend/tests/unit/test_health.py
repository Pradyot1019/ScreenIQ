"""Phase 0 tests: probes, request IDs, RFC 7807 error shape. No DB required."""

from httpx import AsyncClient


async def test_health_ok(client: AsyncClient) -> None:
    for path in ("/health", "/api/v1/health"):
        r = await client.get(path)
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


async def test_request_id_generated_and_echoed(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert len(r.headers["X-Request-ID"]) == 32
    r = await client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


async def test_unknown_route_returns_problem_json(client: AsyncClient) -> None:
    r = await client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert set(body) >= {"type", "title", "status", "detail", "instance"}
    assert body["status"] == 404
    assert body["instance"] == "/api/v1/does-not-exist"


async def test_wrong_method_is_405(client: AsyncClient) -> None:
    r = await client.post("/health")
    assert r.status_code == 405
    assert r.json()["status"] == 405
