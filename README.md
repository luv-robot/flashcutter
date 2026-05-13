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

### Font for Chinese / CJK text overlays

The renderer uses FFmpeg's `drawtext` filter for `text_overlays`, `subtitle_bar`,
`intro_card`, and `outro_card`. `drawtext` requires a font file and the
default font does not support Chinese characters — Chinese copy will render
as empty boxes if no CJK font is configured.

The backend resolves the font path in this order:

1. `FLASHCUTTER_FONT_PATH` environment variable, if set and the file exists.
2. System fallbacks: macOS PingFang / STHeiti / Hiragino, Linux Noto CJK /
   WenQuanYi, then Helvetica / DejaVu.

On macOS the system PingFang is picked up automatically. To force a specific
font (e.g. for production deployments), set:

```bash
export FLASHCUTTER_FONT_PATH=/path/to/your-font.ttc
```

The installed FFmpeg must be built with `--enable-libfreetype` and
`--enable-libharfbuzz`. Default Homebrew `ffmpeg` may lack these. If
`ffmpeg -filters | grep drawtext` returns nothing, reinstall via:

```bash
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg
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

### Template JSON v1

Templates are designed to be readable by operators with video-editing context.
The current renderer still concatenates clips, but templates now describe the
creative goal, editing rules, delivery format, and review notes. Internally,
these operator-facing fields are normalized into render-plan fields.

```json
{
  "type": "concat",
  "creative_goal": {
    "title": "New user acquisition cutdown",
    "audience": "cold traffic",
    "selling_points": ["fast setup", "human-shot proof"],
    "tone": "direct-response"
  },
  "editing": {
    "cut_style": "fixed_interval",
    "clip_duration_seconds": 3,
    "target_duration_seconds": 9,
    "max_clip_count": 3,
    "pacing": "fast",
    "keep_original_order": true
  },
  "delivery": {
    "aspect_ratio": "9:16",
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "format": "mp4",
    "fit": "contain",
    "safe_area_top": 0,
    "safe_area_bottom": 160
  },
  "intro_card": {
    "enabled": true,
    "text": "3 秒看懂",
    "subtitle": "亲测 30 天 · 真实记录",
    "duration_seconds": 1.2,
    "background_color": "0x111111",
    "font_color": "white",
    "font_size": 110,
    "subtitle_font_size": 48
  },
  "subtitle_bar": {
    "enabled": true,
    "text": "真实记录 · 30 天亲测",
    "position": "bottom",
    "font_size": 56,
    "font_color": "white",
    "bar_color": "black@0.7",
    "bar_height": 160
  },
  "outro_card": {
    "enabled": true,
    "text": "点击购买",
    "subtitle": "限时优惠 立即领取",
    "duration_seconds": 1.4,
    "background_color": "0xCC3333",
    "font_color": "white",
    "font_size": 130,
    "subtitle_font_size": 48
  },
  "transformations": {
    "brightness": 0.03,
    "contrast": 1.08,
    "saturation": 1.12,
    "playback_speed": 1.03,
    "volume": 0.95,
    "mute_audio": false
  },
  "review_notes": "Confirm creative treatment, source rights, and hook clarity."
}
```

### Visible variant features (intro card / subtitle bar / outro card / safe area)

These four optional sections turn one seed video into many short-ad variants
whose differences are obvious at first glance — the variation lives on the
screen (hook line, bar copy, CTA copy, frame colors), not in subtle filters.

`intro_card` and `outro_card` are full-screen text cards spliced before and
after the seed video. Each is independently toggleable and supports a primary
headline plus an optional subtitle line:

```text
intro_card.enabled              false (default) | true
intro_card.text                 primary headline (required when enabled)
intro_card.subtitle             optional second line
intro_card.duration_seconds     0 < x ≤ 5
intro_card.background_color     ffmpeg color string, e.g. "black", "0x111111"
intro_card.font_color           default "white"
intro_card.font_size            12 – 240
intro_card.subtitle_font_size   12 – 200
```

`outro_card` accepts the same fields. Cards require `delivery.width`,
`delivery.height`, and `delivery.fps` to be set; the renderer pre-generates
each card at the output dimensions and concatenates it with the segments.

`subtitle_bar` is a persistent text bar overlaid on the seed video frames:

```text
subtitle_bar.enabled        false (default) | true
subtitle_bar.text           bar copy (required when enabled)
subtitle_bar.position       "top" | "bottom" | "center"
subtitle_bar.font_size      12 – 160
subtitle_bar.font_color     default "white"
subtitle_bar.bar_color      ffmpeg color with alpha, or "none" (text only)
subtitle_bar.bar_height     20 – 600 pixels
```

Enabling `subtitle_bar` auto-reserves a `safe_area` of matching height on the
relevant edge so the source video is not hidden behind the bar.

`delivery.safe_area_top` and `delivery.safe_area_bottom` reserve pixel-height
bands at the top or bottom of the canvas. The source video is scaled to the
remaining content area and padded with the safe-area offset, instead of being
centered. Useful for 9:16 / 1:1 / 4:5 outputs where you want a clean strip
for captions, hooks, or CTA badges.

### Built-in demo template

A built-in template `hook_cta_demo` ships these four features pre-wired with
Chinese copy ("3 秒看懂" / "真实记录 · 30 天亲测" / "点击购买"). Pick it on
the Create Variants page to render an example without writing any JSON.

Supported `delivery.fit` modes:

```text
original  preserve image inside target canvas when width/height are set
cover     fill target canvas and crop overflow
contain   fit inside target canvas and pad with black
```

If `delivery.width`, `delivery.height`, or `delivery.fps` are set, the renderer
transcodes clips into the target format before concatenation. Without those
fields, it uses the faster concat path.

The older engineering fields are still accepted for compatibility:

```text
segments.segment_seconds
selection.mode
selection.count
selection.max_total_duration
output.width / output.height / output.fps / output.format
layout.fit
```

Supported creative transformation fields:

```text
transformations.brightness      -1.0 to 1.0
transformations.contrast         0.0 to 3.0
transformations.saturation       0.0 to 3.0
transformations.playback_speed   0.5 to 2.0
transformations.volume           0.0 to 3.0
transformations.mute_audio       true or false
```

Use these fields for genuine creative treatment and operator review, not as a
substitute for source rights, meaningful editing, or platform compliance.

Create a template:

```bash
curl -X POST http://127.0.0.1:8000/api/templates \
  -H "Content-Type: application/json" \
  -d '{"name":"first-three","version":1,"json_spec":{"type":"concat","creative_goal":{"title":"First three hook test","audience":"cold traffic","selling_points":["fast setup"],"tone":"direct-response"},"editing":{"cut_style":"fixed_interval","clip_duration_seconds":3,"target_duration_seconds":9,"max_clip_count":3,"pacing":"fast","keep_original_order":true},"delivery":{"aspect_ratio":"source","width":1280,"height":720,"fps":24,"format":"mp4","fit":"original"},"transformations":{"brightness":0.02,"contrast":1.05,"saturation":1.08,"playback_speed":1.0,"volume":1.0},"review_notes":"Check hook clarity and source rights."}}'
```

Task `params_json` can override template sections:

```json
{
  "selection": {
    "count": 5
  },
  "segments": {
    "segment_seconds": 2
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

### Output review and version management

Rendered outputs include lightweight review metadata for operator workflows.

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
  -d '{"review_status":"approved","review_notes":"Ready for ad testing."}'
```

## Frontend MVP

The frontend MVP is a Vite + React + TypeScript dashboard for operators.

Views:

```text
Seed Videos
Templates
Create Variants  create tasks or create-and-render outputs
Tasks
Review Outputs   preview, filter by seed video, and review outputs
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
