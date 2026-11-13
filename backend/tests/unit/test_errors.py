from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import NotFoundError, QuotaExceededError, register_exception_handlers


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/missing")
    async def missing() -> None:
        raise NotFoundError("Job 42 not found")

    @app.get("/quota")
    async def quota() -> None:
        raise QuotaExceededError("Free plan allows 50 screenings/month", upgrade_url="/billing")

    return app


async def test_domain_errors_map_to_problem_details() -> None:
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as c:
        r = await c.get("/missing")
        assert r.status_code == 404
        assert r.json()["detail"] == "Job 42 not found"

        r = await c.get("/quota")
        assert r.status_code == 402
        assert r.json()["upgrade_url"] == "/billing"
