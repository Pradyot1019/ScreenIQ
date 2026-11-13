# ADR 0001: Monorepo with FastAPI backend and Next.js frontend

**Status:** Accepted (Phase 0)

## Decision
One repository with `backend/` (FastAPI, async SQLAlchemy, Alembic, ARQ) and `frontend/`
(Next.js 15 App Router, TypeScript strict). Postgres 16 with pgvector holds both relational data
and embeddings; Redis is the job queue; MinIO stands in for S3 locally.

## Why
- One PR can change an API contract and its client together; CI checks both.
- pgvector avoids running a second database just for talent search.
- `/health` (liveness, no dependencies) and `/ready` (checks DB + Redis, 503 on failure) are
  separate so a slow database never causes a healthy process to be killed.
- Errors follow RFC 7807 so the frontend branches on a stable `type` URI, not on message text.

## Consequences
Two toolchains (uv + npm) in CI. Acceptable for the clarity of a single repo.
