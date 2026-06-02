#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -f "$ROOT_DIR/.env.local" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env.local"
  set +a
fi

if [ ! -x "$ROOT_DIR/backend/.venv/bin/uvicorn" ]; then
  echo "Backend virtualenv is missing. Run: cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install \".[dev]\""
  exit 1
fi

if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  echo "Frontend dependencies are missing. Run: cd frontend && npm install"
  exit 1
fi

cleanup() {
  trap - EXIT INT TERM
  if [ -n "${BACKEND_PID:-}" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID:-}" ]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

echo "Starting backend at http://127.0.0.1:8000"
(
  cd "$ROOT_DIR/backend"
  export FLASHCUTTER_DATABASE_URL="${FLASHCUTTER_DATABASE_URL:-sqlite:///./flashcutter.dev.db}"
  export FLASHCUTTER_STORAGE_ROOT="${FLASHCUTTER_STORAGE_ROOT:-storage}"
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) &
BACKEND_PID=$!

echo "Starting frontend at http://127.0.0.1:5173"
(
  cd "$ROOT_DIR/frontend"
  npm run dev
) &
FRONTEND_PID=$!

wait
