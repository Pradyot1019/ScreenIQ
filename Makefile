.PHONY: up down logs migrate test lint fmt typecheck check fe-check

up:            ## start the whole stack
	docker compose up --build -d
down:
	docker compose down
logs:
	docker compose logs -f api worker
migrate:       ## apply DB migrations inside the api container
	docker compose exec api alembic upgrade head
test:
	cd backend && uv run pytest -q
lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .
typecheck:
	cd backend && uv run mypy app
fe-check:
	cd frontend && npm run lint && npm run typecheck
check: lint typecheck test fe-check   ## everything CI runs
