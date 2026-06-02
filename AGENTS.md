# AGENTS.md

This file gives Codex and other coding agents the project rules of the road.

## Mission

Build flashcutter as an operator-facing MVP for programmatic short-video ad
production from real, rights-cleared human-shot source videos. Favor repeatable
production workflows: upload, segment, template, queue, render, review, approve,
request changes, reject, or discard.

## Working Directory

Use the repository root:

```text
/Users/luwei/Documents/Codex/flashcutter
```

## Commands

Backend tests:

```bash
cd backend
./.venv/bin/python -m pytest
```

Frontend build:

```bash
cd frontend
npm run build
```

Run both dev servers:

```bash
scripts/dev.sh
```

Full local smoke path:

```bash
scripts/smoke_all.sh
```

## Development Guidelines

- Read the current code before editing; the MVP already has backend, frontend,
  templates, queueing, rendering, and review foundations.
- Keep template JSON operator-readable. Prefer fields that creative/video
  operators can understand.
- Use FFmpeg for media behavior rather than pretending media work is complete.
- Add backend tests for API, model, and rendering behavior when changing those
  surfaces.
- Keep frontend controls direct and operational. This is a dashboard, not a
  marketing site.
- Avoid broad refactors while the MVP loop is still being hardened.

## Safety Boundaries

- Do not build features whose purpose is bypassing platform detection.
- Do not remove review and rights-check language from templates or workflows.
- Do not assume local MVP auth is production-grade.
- Do not replace local files or generated media unless the task calls for it.

## Current Priority Order

1. Template editing and validation.
2. More durable task state history.
3. Richer review feedback.
4. FFmpeg aspect-ratio and failure hardening.
