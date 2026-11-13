"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="ScreenIQ API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # explicit allow-list, never "*"
        allow_credentials=True,  # needed for the httpOnly refresh cookie (Phase 1)
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Location"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    app.include_router(api_router)
    # Probes also at the root, where platforms like Render/Fly look by default.
    app.include_router(health.router)
    return app


app = create_app()
