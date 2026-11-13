#!/bin/sh
# Production entrypoint (Render): migrate, then run the API and the ARQ worker in ONE
# container. Render's free plan has no free background workers, so the worker shares
# the web service. If either process exits, the container exits and Render restarts it.
set -e

alembic upgrade head

arq app.workers.arq_worker.WorkerSettings &
WORKER_PID=$!

uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips="*" &
API_PID=$!

# Stop as soon as either process dies, so the platform notices and restarts us.
while kill -0 "$WORKER_PID" 2>/dev/null && kill -0 "$API_PID" 2>/dev/null; do
  sleep 5
done
echo "a process exited; shutting down" >&2
kill "$WORKER_PID" "$API_PID" 2>/dev/null || true
exit 1
