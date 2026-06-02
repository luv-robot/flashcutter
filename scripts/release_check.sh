#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Running backend tests"
(
  cd "$ROOT_DIR/backend"
  ./.venv/bin/python -m pytest
)

echo "Building frontend"
(
  cd "$ROOT_DIR/frontend"
  npm run build
)

echo "Checking shell scripts"
bash -n "$ROOT_DIR/scripts/deploy_smoke.sh"
bash -n "$ROOT_DIR/scripts/smoke_all.sh"
bash -n "$ROOT_DIR/scripts/dev.sh"

if command -v docker >/dev/null 2>&1; then
  echo "Validating trial compose file"
  docker compose -f "$ROOT_DIR/docker-compose.trial.yml" config >/dev/null
else
  echo "Docker not found; skipping compose validation"
fi

echo "Release check complete"
