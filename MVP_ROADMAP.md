# MVP Roadmap

## Done

- FastAPI backend with SQLAlchemy and SQLite.
- React + TypeScript + Vite operator dashboard.
- Local upload and remote URL import.
- FFmpeg probing, segmentation, render plans, and MP4 rendering.
- Operator-readable template JSON.
- Creative transformations for brightness, contrast, saturation, playback speed,
  volume, and mute.
- Batch task creation and in-memory queueing.
- Output review statuses.
- Production runs with revision rounds for grouped variant review.
- Structured review change requests for future reproduction tasks.
- Music library split into system-visible tracks and user-private uploads.
- FFmpeg-backed template music replacement.
- Seeded system test music and open-licensed music import support.
- Reusable user video clip library for private uploaded clips.
- AI Clone direction documented: generated clips enter the same video clip
  library as uploaded clips.
- Local phone/password login gate.
- User password change flow.
- Trial-production template contract with upload-precondition language and review checklists.
- Grouped visual template controls, including horizontal mirror, style,
  finishing, motion, transition, and texture options.
- Output review grouped by production run, with pending-first behavior.
- One-click review package download for seed video plus all approved outputs in
  a production run, with size warning.
- Protected built-in trial template library.
- Partner-trial Docker/Compose baseline and release/deploy smoke scripts.
- Server-side auth enforcement switch for controlled trials.
- Local trial dataset with multiple completed render/review samples.

## Current Sprint

1. Validate the local trial dataset through manual operator testing.
2. Run Docker build and Compose smoke in an environment with Docker.
3. Keep task progress history visible enough for operators to inspect what
   happened during import, segmentation, planning, rendering, and verification.
4. Harden FFmpeg fit modes, output verification, and failure reporting.
5. Add visible retry/failure recovery actions for failed tasks.
6. Finish the AI Clone MVP loop with job history, mock/ComfyUI provider
   integration, and generated clip review before wiring clips into templates.

## Next

- Add fixture-based smoke cases for the trial-production template library.
- Add server-side authorization enforcement suitable for controlled partner
  trials.
- Turn structured review feedback into concrete reproduction tasks.
- Add operator confirmation flow for revision parameter suggestions.
- Add retries and visible failure recovery actions.
- Add render-plan inspection in the review workspace.
- Add basic output filtering by status and template.
- Add batch import UI for trial users who should not rely on scripts.
- Add ad-platform export packages after manual zip handoff is validated.

## Later

- Replace in-memory queue with a durable worker system.
- Add Alembic migrations.
- Add object storage support.
- Add production authentication and real SMS verification.
- Add role-based review and approval history.
- Add richer template presets for common ad formats.

## Non-Goals

- Bypassing platform detection.
- Working with unclear or non-rights-cleared source material.
- Building a general consumer video editor.
- Replacing professional creative judgment with fully automatic approvals.
