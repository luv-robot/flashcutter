#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIDEO_PATH="${1:-$ROOT_DIR/backend/storage/temp/url-video.mp4}"

cd "$ROOT_DIR/backend"
export FLASHCUTTER_DATABASE_URL="${FLASHCUTTER_DATABASE_URL:-sqlite:///./flashcutter.dev.db}"
export FLASHCUTTER_STORAGE_ROOT="${FLASHCUTTER_STORAGE_ROOT:-storage}"

if [ ! -f "$VIDEO_PATH" ]; then
  echo "Cached smoke video not found: $VIDEO_PATH"
  echo "Provide a local video path: scripts/smoke_all.sh /path/to/video.mp4"
  exit 1
fi

echo "Running backend tests"
.venv/bin/pytest

echo "Running backend video smoke path with $VIDEO_PATH"
.venv/bin/python scripts/smoke_backend.py "$VIDEO_PATH"

echo "Building frontend"
cd "$ROOT_DIR/frontend"
npm run build

echo "Smoke complete"
