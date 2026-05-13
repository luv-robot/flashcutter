# flashcutter-mvp Handoff

## Intended Codex Project Name

`flashcutter-mvp`

## Current Workspace

```text
/Users/luwei/cc-test/flashcutter
```

Use this directory as the working folder when creating/opening the Codex project.

## Product Direction

flashcutter-mvp is an operator-facing production dashboard for turning real
human-shot seed videos into short-video ad variants. The product loop is:

1. Upload or import a seed video.
2. Segment source footage.
3. Apply operator-readable templates.
4. Queue render jobs.
5. Track render progress.
6. Review outputs.
7. Approve, request changes, reject, or discard outputs.

The project should focus on rights-cleared, meaningful creative re-rendering and
review workflows, not on bypassing platform detection.

## Implemented Baseline

- FastAPI backend with SQLAlchemy and SQLite.
- React + TypeScript + Vite operator dashboard.
- FFmpeg segmentation and render-plan driven output rendering.
- Template JSON with creative goal, editing rules, delivery format, review notes,
  and transformations.
- Creative transformations for brightness, contrast, saturation, playback speed,
  volume, and mute.
- Output review workflow.
- Local in-memory task queue with visible task progress.
- Local phone/password registration and login gate for the frontend MVP.

## Current Dev Services

Backend:

```text
http://127.0.0.1:8000
```

Frontend:

```text
http://127.0.0.1:5173
```

## Verification Commands

Backend:

```bash
cd backend
./.venv/bin/python -m pytest
```

Frontend:

```bash
cd frontend
npm run build
```

## Latest Verified Status

- Backend tests: 13 passing.
- Frontend build: passing.
- Backend dependencies were rebuilt under the current user account.
- Dev servers were started successfully with elevated local binding permission.

## Important Notes

- The local login system is an MVP gate. Before production, replace it with
  server-enforced authentication on protected API routes and real SMS
  verification.
- The current task queue is in-memory and suitable for local MVP work. Replace
  it with Redis/RQ/Celery or another durable worker system when jobs need to
  survive process restarts.
- The copied `.git` state shows many untracked files because the source project
  was already in that state.

## Key Context Files

- `PROJECT_CONTEXT.md`
- `README.md`
- `CODEX_PROJECT_HANDOFF.md`
