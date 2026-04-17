#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MYXON MVP — local dev startup
#
# Starts:
#   1. PostgreSQL + Redis in Docker (docker-compose.dev.yml)
#   2. FastAPI backend  → http://localhost:8000  (with --reload)
#   3. Vite frontend    → http://localhost:5173
#
# Prerequisites:
#   - Docker Desktop running
#   - Python 3.12+ in PATH  (or set PYTHON= below)
#   - Node 20+ / npm in PATH
#
# First run:
#   chmod +x dev.sh && ./dev.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

PYTHON=${PYTHON:-python3}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

log()  { echo -e "\033[1;32m▶ $*\033[0m"; }
warn() { echo -e "\033[1;33m⚠ $*\033[0m"; }
die()  { echo -e "\033[1;31m✖ $*\033[0m"; exit 1; }

# ── 1. Infra ──────────────────────────────────────────────────────────────────
log "Starting PostgreSQL + Redis..."
docker compose -f "$SCRIPT_DIR/docker-compose.dev.yml" up -d --wait \
  || die "Docker compose failed. Is Docker running?"

# ── 2. Backend env ────────────────────────────────────────────────────────────
BACKEND_DIR="$SCRIPT_DIR/backend"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  log "Copying .env.local → backend/.env"
  cp "$SCRIPT_DIR/.env.local" "$BACKEND_DIR/.env"
fi

# ── 3. Python venv ────────────────────────────────────────────────────────────
VENV="$BACKEND_DIR/.venv"
if [ ! -d "$VENV" ]; then
  log "Creating Python venv..."
  $PYTHON -m venv "$VENV"
fi

PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

log "Installing backend dependencies..."
$PIP install -q -r "$BACKEND_DIR/requirements.txt"

# ── 4. DB init + seed ─────────────────────────────────────────────────────────
log "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 20); do
  docker compose -f "$SCRIPT_DIR/docker-compose.dev.yml" exec -T db \
    pg_isready -U myxon -q && break
  sleep 1
done

log "Running seed (skips if already seeded)..."
cd "$BACKEND_DIR"
$PY -m scripts.seed 2>&1 | tail -5 || warn "Seed had issues — check output above"
cd "$SCRIPT_DIR"

# ── 5. Frontend deps ──────────────────────────────────────────────────────────
FRONTEND_DIR="$SCRIPT_DIR/frontend"
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  log "Installing frontend dependencies..."
  npm --prefix "$FRONTEND_DIR" install
fi

# Write frontend .env if missing
if [ ! -f "$FRONTEND_DIR/.env.local" ]; then
  echo "VITE_API_URL=http://localhost:8000" > "$FRONTEND_DIR/.env.local"
fi

# ── 6. Launch (parallel) ─────────────────────────────────────────────────────
log "Starting backend  → http://localhost:8000/docs"
log "Starting frontend → http://localhost:5173"
log "Press Ctrl+C to stop all.\n"

# Trap Ctrl+C and kill child processes
cleanup() {
  echo ""
  log "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  docker compose -f "$SCRIPT_DIR/docker-compose.dev.yml" stop
  log "Done."
}
trap cleanup INT TERM

# Backend
cd "$BACKEND_DIR"
"$VENV/bin/uvicorn" app.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  --log-level info \
  2>&1 | sed 's/^/[backend] /' &
BACKEND_PID=$!

# Frontend
cd "$FRONTEND_DIR"
npm run dev -- --host 0.0.0.0 \
  2>&1 | sed 's/^/[frontend] /' &
FRONTEND_PID=$!

wait
