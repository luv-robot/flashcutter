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
- Local phone/password login gate.
- Visible-variant template features (2026-05-13):
  - `intro_card` and `outro_card` — full-screen text cards spliced before
    and after the seed video.
  - `subtitle_bar` — persistent top / bottom / center bar overlay.
  - `delivery.safe_area_top` / `safe_area_bottom` — pixel bands reserved
    for caption / hook / CTA strips.
  - Built-in demo template `hook_cta_demo`.
  - Frontend form fields (collapsible sections) for all four.
- CJK-capable `drawtext` font resolution (`FLASHCUTTER_FONT_PATH` env var
  with macOS / Linux fallbacks). Fixes Chinese text rendering as empty
  boxes in every `text_overlays`-based path, not only the new features.

## Current Sprint

1. Persist task progress history so operators can inspect what happened.
2. Expand review feedback capture beyond a single note field.
3. Harden FFmpeg fit modes, output verification, and failure reporting.
4. Operator UX polish on Create Variants and Review Outputs based on first
   real test-user feedback against the visible-variant features.

## Next

- Add fixture-based smoke cases for common ad cutdown formats.
- Make batch variant creation and review the primary dashboard loop.
- Add retries and visible failure recovery actions.
- Add render-plan inspection in the review workspace.
- Add basic output filtering by status and template.

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
