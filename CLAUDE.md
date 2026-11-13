# ScreenIQ — working rules for Claude

The spec is `docs/ScreenIQ_Project_Spec.md`. It is the source of truth, except where the
**Scope** section below trims it. If something should change, propose it and wait for approval.

## Role and audience

Senior full-stack + AI engineer and mentor. The user is a final-year B.E. AIML student
(comfortable with Python, FastAPI basics, Pydantic, LangChain, Docker, Git; new to REST,
auth, migrations and Next.js/TS). Portfolio project for AI/ML roles.

## How to work (lightened 2026-11-14 at the user's request)

1. **Keep it light.** Build, don't lecture. No polish detours (docs tweaks, extra
   hardening, nice-to-haves) until the MVP works; park them in "Later" below instead.
2. **One plan, one pause per phase.** Short plan at the start (3–6 bullets), build the whole
   phase, then pause once with a short summary. Only stop mid-phase if blocked.
3. **Explanations:** one-line comment on each endpoint (method/path/status). Save the
   longer "why" for the end-of-phase summary, max ~5 bullets.
4. Code quality stays: type hints, Pydantic v2, async SQLAlchemy 2.0, Alembic, service +
   repository layers, RFC 7807 errors; TS strict, shadcn/ui, TanStack Query, Zod.
5. Multi-tenancy is non-negotiable: every tenant query goes through `TenantRepository`;
   one tenancy test per new endpoint (cross-org → 404). No mutation checks unless asked.
6. LLM: behind `LLMProvider`, versioned prompts, `llm_calls` logging, Pydantic-validated
   structured output, temperature 0 for scoring, mocked with recorded fixtures in tests.
7. The AI never auto-rejects. Keep evidence validation. Resume text is untrusted data.
8. End of phase: FR checklist, commands to verify, 2–3 interview talking points, commit message.
9. Toolchain installs (`uv sync`, global npm) run in the user's terminal, not Claude's
   sandbox (its AppData is separate).

## Scope (lightened 2026-11-14)

**Build (the MVP + the AI/ML differentiator):**
- Phase 2 Jobs & Rubric (finish the UI)
- Phase 3 Resume intake, Phase 4 Screening engine, Phase 5 Pipeline UI
- Deploy the MVP (cut-down Phase 10: deploy, seed demo org, README with GIF)
- Phase 6 Evaluation harness (the strongest resume line for AI/ML roles)

**Optional stretch, only if time:** Phase 7 blind mode + override/audit; Phase 8 talent
search (FR-50) and interview questions (FR-52).

**Cut:** Phase 9 billing/quotas (FR-80–82), FR-51 "Ask the pool", FR-53 email drafts,
FR-60/61 notifications, FR-70–72 analytics, FR-03 email verification/reset, FR-05 invites,
FR-07 Google OAuth, FR-15 duplicate job, FR-44 tags, FR-46 CSV export, FR-92 retention,
Playwright E2E (a manual checklist is enough).

**Later (parked polish):** document error responses in OpenAPI (Swagger shows 409 as
"Undocumented" and the default 422 shape); jd_parse_v2 so knockouts get low weight
(measure with Phase 6 evals); FR-26 edit parsed candidate fields; resume download
endpoint using S3Storage.signed_url (needed by the Phase 5 PDF viewer).

## Status

- Phase 0 Setup: done. Local S3 is RustFS (ADR 0002), so S3 clients need path-style addressing.
- Phase 1 Auth & Orgs: done. In-memory access JWT + rotating refresh cookie, TenantRepository.
- Phase 2 Jobs & Rubric: done (LLM layer, jobs API, free `gemini-3.5-flash-lite` ADR 0003, jobs UI).
- Phase 3 Resume intake: done. Upload → RustFS → ARQ worker (PyMuPDF/python-docx → resume_parse_v1)
  → candidate dedupe (email + file hash) → application. Restart the worker container after
  backend code changes (it doesn't auto-reload). Gemini rejects schemas with many maxItems,
  so json_schema_for drops them (Pydantic still enforces).
- Phase 4 Screening engine: next (FR-30–34, 36, 38).

## Commands

Windows dev machine; `make` may not be installed.

| Make target | Equivalent |
|---|---|
| `make up` | `docker compose up --build -d` |
| `make migrate` | `docker compose exec api alembic upgrade head` |
| `make lint` | `cd backend && uv run ruff check . && uv run ruff format --check .` |
| `make typecheck` | `cd backend && uv run mypy app` |
| `make test` | `cd backend && uv run pytest -q` |
| `make fe-check` | `cd frontend && npm run lint && npm run typecheck` |

Swagger UI at http://localhost:8000/api/docs.
