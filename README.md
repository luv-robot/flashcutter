# flashcutter
Build an MVP for a programmatic short-video ad production system based on real human-shot source videos, template-based editing,FFmpeg rendering, task queue,and human review feedback.

## Backend MVP

The backend MVP uses FastAPI, SQLAlchemy, SQLite, Pydantic, pytest, and FFmpeg.
It currently supports a synchronous smoke path for uploading a video, splitting it
into fixed-interval segments, generating a concat render plan, and rendering one
local MP4 output.

## Recommended local workflow

Keep dependencies and test media local. Use remote video URLs only for occasional
integration checks.

1. Install backend dependencies once:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install ".[dev]"
```

2. Install frontend dependencies once:

```bash
cd frontend
npm install
```

3. Keep a cached local test video, for example:

```text
backend/storage/temp/url-video.mp4
```

4. Start both dev servers:

```bash
scripts/dev.sh
```

5. Run local smoke without network access:

```bash
scripts/smoke_all.sh
```

Or pass any local video:

```bash
scripts/smoke_all.sh /path/to/source.mp4
```

Local configuration can be copied from:

```text
.env.example
```

Run the release check before cutting a partner trial build:

```bash
scripts/release_check.sh
```

After deploying a trial backend, run:

```bash
scripts/deploy_smoke.sh
```

Public-cloud trial deployment notes live in:

```text
DEPLOYMENT.md
```

Template and component design notes:

```text
docs/template_system_v3.md
docs/template_component_library.md
docs/ad_platform_export_design.md
docs/comfyui_infra_options.md
docs/ai_clone_development_plan.md
docs/ai_clone_comfyui_workflow_build.md
docs/OPERATOR_USER_GUIDE.md
```

Current trial release notes:

```text
TRIAL_V0_1_RELEASE.md
```

### Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install ".[dev]"
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Backend API docs:

```text
http://127.0.0.1:8000/docs
```

Operator dashboard:

```text
http://127.0.0.1:5173
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### Run tests

```bash
cd backend
pytest
```

### Run the backend smoke path

The smoke path exercises upload, fixed-interval FFmpeg splitting, task creation,
render-plan creation, and one FFmpeg output render.

Create a local sample video:

```bash
cd backend
mkdir -p storage/temp
ffmpeg -y \
  -f lavfi -i testsrc=duration=9:size=1280x720:rate=30 \
  -f lavfi -i sine=frequency=1000:duration=9 \
  -c:v libx264 -c:a aac -pix_fmt yuv420p storage/temp/sample.mp4
```

Run the smoke script:

```bash
python scripts/smoke_backend.py storage/temp/sample.mp4
```

Or exercise the API manually while `uvicorn app.main:app --reload` is running:

```bash
curl -F "file=@storage/temp/sample.mp4" http://127.0.0.1:8000/api/assets/upload
curl -X POST "http://127.0.0.1:8000/api/assets/1/segment?segment_seconds=3"
curl http://127.0.0.1:8000/api/templates
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke-test","asset_id":1,"template_id":1,"params_json":{}}'
curl -X POST http://127.0.0.1:8000/api/tasks/1/render-plan
curl -X POST http://127.0.0.1:8000/api/tasks/1/render
curl http://127.0.0.1:8000/api/outputs
```

Import a remote video URL and run the pipeline in one call after creating a task:

```bash
curl -X POST http://127.0.0.1:8000/api/assets/import-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/video.mp4","filename":"source.mp4"}'

curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"name":"url-smoke","asset_id":1,"template_id":1,"params_json":{}}'

curl -X POST http://127.0.0.1:8000/api/tasks/1/run \
  -H "Content-Type: application/json" \
  -d '{"segment_seconds":3}'
```

### Template JSON v2

Templates are now v2 variant recipes. The current renderer still concatenates
clips, but the production contract is modular: a recipe combines an ad
`blueprint`, `render_preset`, `style_pack`, optional `copy_pack`, slot bindings,
music policy, and review notes. Source authorization is expected to be completed
before upload by the trial partner; flashcutter does not automate rights
verification. Internally, recipes are compiled into renderer-facing fields.

Full design:

```text
docs/ad_variant_template_v2.md
```

Next template-system design focused on designer/operator usability:

```text
docs/template_system_v3.md
```

```json
{
  "schema_version": 2,
  "type": "variant_recipe",
  "recipe_id": "problem_demo_cta.vertical.clean.see_the_fix",
  "name": "prod_problem_demo_cta_vertical_clean",
  "blueprint": {
    "blueprint_id": "problem_demo_cta_v1",
    "name": "Problem demo CTA",
    "creative_goal": {
      "title": "Problem demo CTA",
      "audience": "cold traffic",
      "selling_points": ["clear user pain", "human-shot product demo"],
      "tone": "direct-response"
    },
    "production_contract": {
      "use_case": "First-pass performance ad from rights-cleared UGC footage.",
      "operator_notes": "Use when the source has a visible problem moment followed by product use.",
      "review_checklist": ["Opening seconds communicate the problem."]
    },
    "editing": {
      "cut_style": "fixed_interval",
      "clip_duration_seconds": 2.5,
      "target_duration_seconds": 10,
      "max_clip_count": 4,
      "pacing": "fast",
      "keep_original_order": true
    },
    "slots": [{"slot": "hook", "role": "source_segment"}]
  },
  "render_preset": {
    "preset_id": "vertical_9_16_cover",
    "name": "Vertical 9:16 cover",
    "delivery": {"aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 30, "format": "mp4", "fit": "cover"}
  },
  "style_pack": {
    "style_pack_id": "clean_ad",
    "name": "Clean ad",
    "transformations": {"visual_style": "clean_ad", "contrast": 1.12, "saturation": 1.16}
  },
  "copy_pack": {
    "copy_pack_id": "see_the_fix_cta",
    "name": "See the fix CTA",
    "text_overlays": [{"text": "SEE THE FIX", "x": 96, "y": 1592, "font_size": 62}]
  },
  "review_notes": "Confirm pain clarity, demo visibility, and CTA readability."
}
```

Supported `delivery.fit` modes:

```text
original  preserve image inside target canvas when width/height are set
cover     fill target canvas and crop overflow
contain   fit inside target canvas and pad with black
```

If `delivery.width`, `delivery.height`, or `delivery.fps` are set, the renderer
transcodes clips into the target format before concatenation. Without those
fields, it uses the faster concat path.

Older complete-template JSON is no longer part of the supported template
contract. Use v2 recipes and let `template_compiler.py` produce renderer fields.

Supported creative transformation fields:

```text
transformations.brightness      -1.0 to 1.0
transformations.contrast         0.0 to 3.0
transformations.saturation       0.0 to 3.0
transformations.playback_speed   0.5 to 2.0
transformations.volume           0.0 to 3.0
transformations.mute_audio       true or false
```

Operator-facing grouped visual controls compile into FFmpeg filters:

```text
transformations.orientation        normal | mirror_horizontal
transformations.visual_style       natural | clean_ad | warm_lifestyle | cool_tech | punchy_social | soft_beauty
transformations.finishing_style    none | sharpen | soften | film_grain | vignette
transformations.motion_style       none | slow_push_in | slow_pan | light_rotate | social_pulse
transformations.transition_style   hard_cut | flash_white | flash_black | soft_fade
transformations.texture_style      none | warm_light_leak | cool_light_leak | subtle_grid
```

These options are intentionally visible creative treatments. Flashcutter should
not add hidden, near-invisible, or hardware-spoofing changes whose purpose is to
bypass platform originality, review, or detection systems.

Supported music fields:

```text
music.mode       replace
music.track_id   selected system or private music track id
music.volume     0.0 to 3.0
music.loop       true or false
```

When `music.track_id` is set, the renderer replaces the original video audio
with the selected music track. The output audio is encoded to AAC in the final
MP4. If `music.loop` is true, short music tracks are looped and then cut to the
video duration.

Use these fields for genuine creative treatment and operator review, not as a
substitute for source rights, meaningful editing, or platform compliance.

Create a custom recipe by posting v2 `json_spec`:

```bash
curl -X POST http://127.0.0.1:8000/api/templates \
  -H "Content-Type: application/json" \
  -d '{"name":"custom-problem-demo","version":1,"json_spec":{"schema_version":2,"type":"variant_recipe","recipe_id":"custom.problem_demo.vertical","name":"custom-problem-demo","blueprint":{"blueprint_id":"problem_demo_cta_v1","name":"Problem demo CTA","creative_goal":{"title":"Problem demo CTA"},"production_contract":{"use_case":"Rights-cleared source cutdown.","operator_notes":"Use pre-cleared source footage only.","review_checklist":["Opening problem is clear."]},"editing":{"cut_style":"fixed_interval","clip_duration_seconds":2.5,"target_duration_seconds":10,"max_clip_count":4},"slots":[]},"render_preset":{"preset_id":"vertical_9_16_cover","name":"Vertical 9:16 cover","delivery":{"aspect_ratio":"9:16","width":1080,"height":1920,"fps":30,"format":"mp4","fit":"cover"}},"style_pack":{"style_pack_id":"clean_ad","name":"Clean ad","transformations":{"visual_style":"clean_ad","contrast":1.12}},"review_notes":"Check hook clarity and product visibility."}}'
```

Task `params_json` can override recipe sections:

```json
{
  "recipe": {
    "slot_bindings": {
      "hook": {
        "source_type": "ai_asset",
        "asset_type": "hook",
        "tags": ["cat", "funny"],
        "duration": [2, 4],
        "optional": true
      }
    }
  }
}
```

Create multiple tasks for one seed video and many templates:

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/batch \
  -H "Content-Type: application/json" \
  -d '{"name_prefix":"seed-video-variant","asset_id":1,"template_ids":[1,2,3],"params_json":{}}'
```

Create and render multiple variants in one call:

```bash
curl -X POST http://127.0.0.1:8000/api/assets/1/render-variants \
  -H "Content-Type: application/json" \
  -d '{"name_prefix":"seed-video-variant","template_ids":[1,2,3],"params_json":{}}'
```

Each batch creates a `production_run`. Tasks and review outputs include:

```text
production_run_id
production_run_name
revision_number
```

Use `production_run_id` in a later batch request to create a new revision round
inside the same production run. The backend assigns `revision_number` as the
current maximum revision in that run plus one.

### Music Library

The trial app separates music into a system public library and each user's
private library. Operators can upload private audio tracks and browse/play both
system and private tracks from the dashboard.

List visible music tracks:

```bash
curl http://127.0.0.1:8000/api/music
```

Upload a private music track:

```bash
curl -X POST http://127.0.0.1:8000/api/music/upload \
  -F "title=Light opener" \
  -F "file=@/path/to/music.mp3"
```

Seed generated system test music:

```bash
cd backend
./.venv/bin/python scripts/seed_system_music.py
```

The seed script creates four synthetic system tracks for trial rendering tests:

```text
System Bright Pulse
System Calm Bed
System Clean Drive
System Soft Resolve
```

Import a batch of open-licensed system music from Wikimedia Commons:

```bash
cd backend
./.venv/bin/python scripts/import_open_music.py
```

The open-music importer is curated for fast, energetic ad backgrounds and stores
artist, source URL, license URL, attribution text, mood, and BPM on each system
track. Current imports use CC BY 4.0 tracks, so downstream ad/package workflows
should preserve attribution metadata.

Music tracks are applied by the renderer when a template sets `music.track_id`.
The trial behavior is simple and explicit: the selected music replaces original
audio. The app does not infer whether the original audio is music or speech.

### AI Clips Factory MVP

The AICF direction has been narrowed to AI Clone. The current product direction
is documented in [`docs/ai_clips_factory.md`](docs/ai_clips_factory.md):
Flashcutter only keeps a prompt-driven imitation workflow for reference images
or reference videos. More complex generation control belongs in a separately
deployed ComfyUI instance, connected through backend APIs.

Generated clips and uploaded reusable clips are treated as the same user video
asset class in the operator UI. The `视频片段` page should host the clone entry,
then list generated and uploaded private video clips together for template slot
selection.

Implemented asset types:

```text
hook
cta
broll
reaction
meme
product_motion
```

Implemented asset kinds:

```text
video
image
```

List visible generated/uploaded clip assets for the authenticated user:

```bash
curl http://127.0.0.1:8000/api/ai-assets \
  -H "Authorization: Bearer $FLASHCUTTER_TOKEN"
```

Filter by type, kind, scope, or tag:

```bash
curl "http://127.0.0.1:8000/api/ai-assets?asset_type=hook&tag=surprised" \
  -H "Authorization: Bearer $FLASHCUTTER_TOKEN"
```

Upload a private reusable clip:

```bash
curl -X POST http://127.0.0.1:8000/api/ai-assets/upload \
  -H "Authorization: Bearer $FLASHCUTTER_TOKEN" \
  -F "title=Surprise hook" \
  -F "asset_type=hook" \
  -F "provider=manual" \
  -F "tags=hook,surprised,cute" \
  -F "prompt=Surprised reaction for a fast opening hook" \
  -F "file=@/path/to/clip-or-image.mp4"
```

AI Clone should create another private reusable clip in the same video clip
library. The current local-motion endpoint is only a local MVP stub and should
be replaced by the AI Clone job flow:

```bash
curl -X POST http://127.0.0.1:8000/api/ai-assets/generate/local-motion \
  -H "Authorization: Bearer $FLASHCUTTER_TOKEN" \
  -F "title=Generated hook" \
  -F "asset_type=hook" \
  -F "duration_seconds=3" \
  -F "tags=hook,generated" \
  -F "prompt=Turn this reference image into a short opening hook" \
  -F "file=@/path/to/reference.png"
```

Legacy provider and generator interfaces live under:

```text
backend/app/services/ai_asset_factory/
```

Do not extend this toward direct multi-provider generation. New generation work
should follow the AI Clone design and begin with a mock ComfyUI/clone client.

### Output review and version management

Rendered outputs include lightweight review metadata for operator workflows.
Production runs have batch-level status. Operators mark a whole batch
`needs_revision` manually after reviewing individual variants; a single variant
marked `needs_changes` does not automatically trigger batch reproduction.

Review statuses:

```text
pending_review
approved
rejected
needs_changes
```

List all outputs with seed video, task, and template context:

```bash
curl http://127.0.0.1:8000/api/outputs/review
```

List all output versions for one seed video:

```bash
curl http://127.0.0.1:8000/api/assets/1/outputs
```

Update review status and notes:

```bash
curl -X PATCH http://127.0.0.1:8000/api/outputs/1/review \
  -H "Content-Type: application/json" \
  -d '{"review_status":"needs_changes","review_notes":"Needs a clearer hook.","change_requests":[{"category":"copy","target":"opening caption","request":"Make the hook more direct.","priority":"high"}],"tags":["hook","copy"]}'
```

Structured `change_requests` are stored with review feedback so later
reproduction work can consume categories such as `copy`, `crop`, `pacing`,
`music`, `template`, `asset_selection`, and `other`.

Approved outputs in one production run can be packaged for handoff before ad
platform connectors are available. The package contains the seed video and all
approved outputs in that run. The UI must show an estimated raw size warning
before starting the download.

Estimate package size:

```bash
curl http://127.0.0.1:8000/api/production-runs/1/package/estimate
```

Download package:

```bash
curl -L http://127.0.0.1:8000/api/production-runs/1/package -o review-package.zip
```

## Auth and account operations

The local trial uses phone/password login. Auth is enough for controlled partner
trials, but not production-grade public signup.

Authenticated users can change their own password from the dashboard or API:

```bash
curl -X PATCH http://127.0.0.1:8000/api/auth/password \
  -H "Authorization: Bearer $FLASHCUTTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password":"trial-secret","new_password":"new-strong-password"}'
```

Changing the password keeps the current session active and affects future
logins.

## Frontend MVP

The frontend MVP is a Vite + React + TypeScript dashboard for operators.

Views:

```text
Seed Videos        upload/import rights-cleared seed videos
Templates          manage operator-readable template methods
Create Variants    create tasks or create-and-render outputs
Tasks              inspect queue state and failures
Review Outputs     grouped by production run; approve, reject, request changes, package approved videos
Music Library      system public tracks plus user-private uploads with playback
Video Clips        upload reusable clips and launch AI Clone from references
```

Run the backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

Run the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Build:

```bash
cd frontend
npm run build
```
