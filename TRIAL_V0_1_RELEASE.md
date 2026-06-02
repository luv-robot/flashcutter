# flashcutter Trial v0.1

This release is the first controlled partner-trial baseline. It is intended for
small-scale external evaluation with rights-cleared source videos and a known
operator account.

## Scope

- Upload or import seed videos.
- Segment source footage with FFmpeg.
- Use the built-in trial-production template library.
- Create single or batch generation tasks.
- Render MP4 outputs.
- Review outputs with source, template, render-plan intent, and feedback context.
- Review outputs by production run, with the pending review batches surfaced
  first.
- Inspect render-plan clips, output settings, layout, transformations, and
  production contract from the review workspace.
- Mark outputs as approved, needs changes, rejected, or discarded.
- Package a production run's seed video plus approved outputs into a zip for
  manual partner handoff after confirming the estimated size warning.
- Manage a system/private music library, preview tracks, and render templates
  that replace original audio with selected music.
- Upload private reusable video clips. AI Clone outputs should enter the same
  clip library once the generation MVP is completed.
- Change the current account password from the dashboard.

## Template Library

Trial v0.1 ships with 10 built-in production templates:

- `prod_pain_demo_cta_vertical`
- `prod_fast_hook_proof_vertical`
- `prod_silent_caption_vertical`
- `prod_source_frame_offer_banner`
- `prod_square_social_proof`
- `prod_clean_cutdown_no_overlay`
- `prod_product_closeup_detail`
- `prod_testimonial_reaction`
- `prod_before_after_square`
- `prod_unboxing_setup_steps`

Built-in templates are protected. Operators can edit and save them as custom
templates, but cannot overwrite or delete the built-in baseline.

## Local Trial State

The current local trial environment has been seeded with:

- 10 templates
- system test music
- sample seed videos and reviewable outputs for manual smoke testing

Local web services:

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8000
Docs:     http://127.0.0.1:8000/docs
```

Local test account:

```text
phone: +15550000000
password: trial-secret
```

## Manual Test Checklist

1. Log in with the local test account.
2. Open Templates and confirm all 10 built-in templates appear.
3. Edit a built-in template and confirm the save action creates a custom copy.
4. Open Music Library and confirm system tracks can be played.
5. Open Video Clips and upload a short private clip.
6. Open Review and inspect rendered outputs grouped by production run.
7. Confirm each output shows production intent and review checklist context.
8. Expand Render Plan and confirm clip count, output settings, fit mode, and
   transformations are visible.
9. Change one output from `needs_changes` to `approved`.
10. Download the review package for a run with approved outputs after checking
    the size warning.
11. Open Tasks and inspect task progress/events for completed renders.
12. Open Create Variants, select one sample asset and several templates, then run
   a small queued batch.
13. Confirm new outputs appear in Review.
14. Change the test account password and verify the new password works on the
    next login.

## Release Check

Before tagging or deploying:

```bash
scripts/release_check.sh
```

The current verified check result:

```text
Backend tests: 38 passed
Frontend build: passing
Shell script syntax check: passing
Docker Compose validation: skipped when Docker is unavailable
```

## Deployment Smoke

Basic remote smoke:

```bash
FLASHCUTTER_SMOKE_API_BASE=https://your-api.example.com \
FLASHCUTTER_SMOKE_PHONE="+15551234567" \
FLASHCUTTER_SMOKE_PASSWORD="replace-with-strong-password" \
scripts/deploy_smoke.sh
```

Full render smoke:

```bash
FLASHCUTTER_SMOKE_API_BASE=https://your-api.example.com \
FLASHCUTTER_SMOKE_PHONE="+15551234567" \
FLASHCUTTER_SMOKE_PASSWORD="replace-with-strong-password" \
FLASHCUTTER_SMOKE_VIDEO=/path/to/smoke.mp4 \
FLASHCUTTER_SMOKE_RENDER=true \
scripts/deploy_smoke.sh
```

## Known Trial Limits

- Sessions are in-memory. A backend restart requires login again.
- SQLite is used for controlled single-instance trials only.
- Rendering queue is in-memory and not durable across restarts.
- Object storage is not yet integrated.
- AI Clone is documented and partially stubbed, but the production job/history
  loop is still future work.
- Generated or uploaded reusable clips are not yet fully integrated into
  template slot selection.
- Ad platform connectors are not available yet; review-package zip download is
  the current manual handoff bridge.
- Docker image build has not been verified in this local environment because
  Docker is unavailable.
- Auth is sufficient for controlled trials, not broad public production.

## Recommended Next Work

- Run Docker build and `docker compose -f docker-compose.trial.yml up --build`
  in an environment with Docker.
- Add fixture-based render smoke tests for multiple templates.
- Add visible retry/failure recovery actions in the task queue.
- Add render-plan inspection directly in the review workspace.
- Replace in-memory sessions before multi-instance cloud deployment.
