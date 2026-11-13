# ScreenIQ

Multi-tenant, explainable AI resume screening. Every score cites verbatim evidence from the
resume, and a human always makes the final decision. Full spec: `docs/ScreenIQ_Project_Spec.md`.

**Status:** Phase 0 (setup) complete. Next: Phase 1, Auth & Orgs.

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env
make up                                  # postgres+pgvector, redis, rustfs, api, worker, frontend
curl localhost:8000/health               # {"status":"ok"}
curl localhost:8000/ready                # {"status":"ready","checks":{"database":true,"redis":true}}
open http://localhost:3000               # green "API ok" dot
open http://localhost:8000/api/docs      # Swagger UI
open http://localhost:9001/rustfs/console/  # RustFS S3 console (minioadmin / minioadmin)
```

## Local dev without Docker for the app code

```bash
docker compose up -d postgres redis rustfs s3-init
cd backend && cp .env.example .env && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload            # API on :8000
uv run arq app.workers.arq_worker.WorkerSettings # worker
cd ../frontend && npm install && npm run dev     # UI on :3000
```

## Quality gates

`make check` runs ruff, ruff format, mypy (strict), pytest, ESLint and `tsc --noEmit`.
CI (`.github/workflows/ci.yml`) runs the same, plus migrations against a real pgvector Postgres.

## Layout

```
backend/app/core      config, JSON logging, request-id middleware, RFC 7807 errors
backend/app/api/v1    routers (health now; auth, jobs, … per phase)
backend/app/db        async engine/session, declarative Base with naming convention
backend/app/workers   ARQ worker (ping task now; parse/screen in Phases 3–4)
backend/alembic       migrations (0001 enables pgvector + citext)
frontend/lib          typed fetch client (Zod-validated), schemas
docs/ADRs             architecture decision records
```
