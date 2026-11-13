FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/usr/local
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
# Runtime dependencies only: tests and linters run in CI, never in the container.
RUN uv sync --no-install-project --no-dev

COPY . .
EXPOSE 8000
# Production: migrate, then API + worker in one container (see start.sh).
# docker-compose overrides this for local dev (separate api/worker, auto-reload).
CMD ["sh", "./start.sh"]
