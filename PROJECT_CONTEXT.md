# flashcutter Project Context

## Product Goal

flashcutter is an MVP for programmatic short-video ad production from real
human-shot source videos. The product direction is template-based editing,
FFmpeg rendering, task orchestration, and human review feedback.

## Positioning And Users

The product is an operator-facing production dashboard, not a consumer editor.
Its core user is a growth, creative, or video operations person who needs to turn
one seed video into many short ad variants, inspect the results, and mark outputs
for ad testing or revision.

The system should favor repeatable production workflows over one-off manual
editing. Templates should stay readable to people with video-editing context and
describe creative goals, editing rules, delivery format, and review notes.

## Core Workflow

1. Add or import a seed video.
2. Segment source footage into reusable clips.
3. Create templates that describe the cutdown strategy and delivery format.
4. Create one task or batch tasks for a seed video and one or more templates.
5. Generate render plans and FFmpeg outputs.
6. Review rendered outputs with seed video, task, and template context.
7. Mark outputs as `pending_review`, `approved`, `rejected`, or `needs_changes`.
8. Package one production run's seed video plus approved outputs for manual
   handoff before ad platform connectors are ready.

## Current Stack

- Backend: FastAPI, SQLAlchemy, SQLite, Pydantic, pytest, FFmpeg
- Frontend: React, TypeScript, Vite
- Local workflow scripts: `scripts/dev.sh`, `scripts/smoke_all.sh`
- Trial deployment: Dockerized backend/frontend, persistent storage volume,
  configurable CORS, and `scripts/release_check.sh`

## Important Paths

- Backend app: `backend/app`
- Backend tests: `backend/tests`
- Frontend app: `frontend/src`
- Local storage and generated media: `backend/storage`
- Smoke script: `backend/scripts/smoke_backend.py`
- Trial deployment guide: `DEPLOYMENT.md`
- Trial release notes: `TRIAL_V0_1_RELEASE.md`

## Local Commands

Start both dev servers:

```bash
scripts/dev.sh
```

Run backend tests:

```bash
cd backend
./.venv/bin/python -m pytest
```

Build frontend:

```bash
cd frontend
npm run build
```

Run local smoke path:

```bash
scripts/smoke_all.sh
```

## Verified Baseline

- Backend tests: 38 passing
- Frontend production build: passing
- Release check script: passing, with Docker Compose validation skipped when
  Docker is unavailable
- Local trial web services can run at `http://127.0.0.1:5173` and
  `http://127.0.0.1:8000`
- Local trial data includes the protected 10-template trial library, seeded
  system music, and generated review samples for manual testing.

## Near-Term Development Directions

- Move templates to a trial-production contract: renderable JSON plus creative
  goal, upload-precondition language, operator use case, and review checklist.
- Rebuild and maintain the built-in template library as production-facing ad
  formats rather than renderer validation examples.
- Prepare a stable public-cloud trial release for partners, with clear release
  checks, container deployment, health checks, and persistent media storage.
- Add durable task states for import, segment, render-plan, render, and review.
- Expand review feedback capture and connect structured change requests to
  revision rounds.
- Harden FFmpeg render behavior around aspect ratio, fitting, and failures.
- Add fixture-based smoke cases for common ad cutdown formats.
- Make batch variant creation and output review feel like the primary product
  loop in the frontend.
- Continue improving creative re-rendering as a rights-cleared transformation
  workflow, with render-plan metadata that reviewers can inspect.
- Move rendering work through a visible queue so operators can monitor progress
  instead of waiting on long synchronous requests.
- Keep the review workspace focused on approval, change requests, and discarded
  outputs.
- Treat music as a library-backed production input: system-visible tracks plus
  user-private uploads. Trial renderer behavior should replace original audio
  with selected template music rather than trying to infer audio type.
- Treat reusable user video clips and AI Clone outputs as one video-clip asset
  library. AI generation is a way to create clips, not a replacement for the
  core seed-video-to-variant workflow.
- Keep visual transformation options reviewable and visible. Do not implement
  hidden perturbations, hardware spoofing, or other platform-detection bypass
  techniques.
- Treat phone login as the local MVP access gate; replace with SMS verification
  and server-side API enforcement before production use.
- Allow operators to change their own password during controlled trials.
