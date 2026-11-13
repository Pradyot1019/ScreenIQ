"""RFC 7807 "Problem Details" error responses.

Every error the API returns has the same shape:
    {"type": ..., "title": ..., "status": ..., "detail": ..., "instance": ...}
with Content-Type `application/problem+json`. Clients can branch on `type`
instead of parsing human-readable messages.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

PROBLEM_JSON = "application/problem+json"
PROBLEM_BASE = "https://screeniq.dev/problems/"


class AppError(Exception):
    """Base class for domain errors raised by services.

    Services raise these; the handler below turns them into HTTP responses,
    so business logic never has to know about HTTP.
    """

    status: int = 500
    type_: str = "internal-error"
    title: str = "Internal Server Error"
    headers: dict[str, str] | None = None

    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        self.extra = extra


class NotFoundError(AppError):
    status, type_, title = 404, "not-found", "Resource not found"


class ConflictError(AppError):
    status, type_, title = 409, "conflict", "Conflict"


class ForbiddenError(AppError):
    status, type_, title = 403, "forbidden", "Forbidden"


class UnauthorizedError(AppError):
    status, type_, title = 401, "unauthorized", "Not authenticated"
    # HTTP requires a 401 to say which auth scheme the client should use.
    headers = {"WWW-Authenticate": "Bearer"}


class QuotaExceededError(AppError):
    status, type_, title = 402, "quota-exceeded", "Plan quota exceeded"


# 5xx errors caused by an upstream service (the LLM API), not by our own bug.
class BadGatewayError(AppError):
    """502: the upstream answered, but with something unusable (an error or invalid output)."""

    status, type_, title = 502, "upstream-error", "Upstream service error"


class ServiceUnavailableError(AppError):
    """503: the feature can't work right now (e.g. no API key configured)."""

    status, type_, title = 503, "service-unavailable", "Service unavailable"


class GatewayTimeoutError(AppError):
    """504: the upstream didn't answer in time."""

    status, type_, title = 504, "upstream-timeout", "Upstream service timed out"


def problem(
    status: int,
    type_: str,
    title: str,
    detail: str,
    instance: str,
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    body = {
        "type": PROBLEM_BASE + type_,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem(
            exc.status,
            exc.type_,
            exc.title,
            exc.detail,
            request.url.path,
            headers=exc.headers,
            **exc.extra,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = {404: "Not Found", 405: "Method Not Allowed"}.get(exc.status_code, "HTTP Error")
        return problem(
            exc.status_code,
            title.lower().replace(" ", "-"),
            title,
            str(exc.detail),
            request.url.path,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return problem(
            422,
            "validation-error",
            "Validation failed",
            "One or more fields are invalid.",
            request.url.path,
            errors=errors,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error")
        return problem(
            500,
            "internal-error",
            "Internal Server Error",
            "Something went wrong.",
            request.url.path,
        )
