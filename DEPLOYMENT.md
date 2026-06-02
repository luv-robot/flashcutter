# Trial Deployment

This is the deployment baseline for a partner-facing trial build. It is not the
final production architecture, but it should be stable enough for controlled
external use.

## Target

- Backend API: FastAPI, FFmpeg, SQLite, persistent storage volume.
- Frontend: static Vite build served by Nginx.
- Media: stored on a persistent volume mounted at `/data/storage`.
- Database: SQLite at `/data/flashcutter.db` for the trial phase.
- AICF / AI Clone: optional separate GPU node running ComfyUI, connected from
  the backend through private network or a tightly restricted public endpoint.

## UCloud Trial Shape

The selected first cloud deployment shape is UCloud Hong Kong plus a separate
GPU node for AICF testing.

```text
Partner browser
  -> flashcutter-web / flashcutter-api
     UCloud Hong Kong CPU cloud host
       - backend container
       - frontend container or static Nginx
       - SQLite database
       - /data/storage media volume
       - FFmpeg render path
  -> AICF / AI Clone request
     UCloud GPU cloud host
       - ComfyUI
       - model files and workflow runtime
       - generated clip outputs
```

Recommended starting resources:

```text
CPU node:
  Region: Hong Kong
  CPU: 4 vCPU
  Memory: 8 GB
  Disk: 100-200 GB SSD
  Bandwidth: 5-10 Mbps to start

GPU node:
  GPU: RTX 40 series 24 GB to start
  CPU/Memory: provider default for the selected GPU instance is acceptable for trial
  Disk: 200 GB+ SSD, more if model files are stored locally
  Billing: hourly or short-cycle while workflows are still being tested
```

Keep the CPU node and GPU node separate. The CPU node should remain stable for
partner trial usage. The GPU node can be rebuilt, stopped, resized, or replaced
while AI Clone workflows are being tuned.

Object storage is optional for the first trial. Start with the CPU node's
persistent disk. Add UCloud US3 or another object storage service after media
volume, download volume, or backup needs justify it.

## Required Environment

Backend:

```text
FLASHCUTTER_APP_NAME=flashcutter
FLASHCUTTER_ENVIRONMENT=trial
FLASHCUTTER_DATABASE_URL=sqlite:////data/flashcutter.db
FLASHCUTTER_STORAGE_ROOT=/data/storage
FLASHCUTTER_DEFAULT_TEMPLATE_NAME=prod_pain_demo_cta_vertical
FLASHCUTTER_CORS_ORIGINS=https://your-frontend.example.com
FLASHCUTTER_REQUIRE_AUTH=true
FLASHCUTTER_ALLOW_REGISTRATION=true
FLASHCUTTER_AI_CLONE_PROVIDER=comfyui
FLASHCUTTER_COMFYUI_BASE_URL=http://gpu-private-ip:18188
FLASHCUTTER_COMFYUI_API_KEY=
FLASHCUTTER_COMFYUI_TIMEOUT_SECONDS=30
FLASHCUTTER_COMFYUI_POLL_INTERVAL_SECONDS=5
FLASHCUTTER_COMFYUI_MAX_WAIT_SECONDS=900
FLASHCUTTER_AI_CLONE_IMAGE_WORKFLOW_PATH=workflows/ai_clone/image_clone_video_v1/workflow_api.json
FLASHCUTTER_AI_CLONE_VIDEO_WORKFLOW_PATH=workflows/ai_clone/video_clone_clip_v1/workflow_api.json
```

Frontend build:

```text
VITE_API_BASE_URL=https://your-api.example.com
```

If AICF is not ready or the GPU node is unavailable, switch back to the mock
provider without changing the rest of the deployment:

```text
FLASHCUTTER_AI_CLONE_PROVIDER=mock
FLASHCUTTER_COMFYUI_BASE_URL=
```

## Local Container Trial

```bash
docker compose -f docker-compose.trial.yml up --build
```

Frontend:

```text
http://localhost:8080
```

Backend:

```text
http://localhost:8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Release Check

Before tagging a trial release:

```bash
scripts/release_check.sh
```

This runs backend tests, builds the frontend, and validates the Docker Compose
file when Docker is available.

## Trial Account Setup

Create or update the first partner account inside the backend environment:

```bash
cd backend
FLASHCUTTER_DATABASE_URL=sqlite:////data/flashcutter.db \
FLASHCUTTER_STORAGE_ROOT=/data/storage \
python scripts/init_trial_user.py \
  --phone "+15551234567" \
  --password "replace-with-strong-password" \
  --display-name "Partner operator"
```

After the account is created and login is confirmed, disable public
registration:

```text
FLASHCUTTER_ALLOW_REGISTRATION=false
```

Keep authentication enabled in public-cloud trials:

```text
FLASHCUTTER_REQUIRE_AUTH=true
```

## GPU Node Setup

The GPU node is only for AICF / AI Clone. It should not host the partner-facing
web app or the main database.

Minimum setup checklist:

1. Install NVIDIA driver, Docker, and NVIDIA Container Toolkit, or use a UCloud
   GPU image that already includes them.
2. Deploy ComfyUI and expose it on an internal port, for example `18188`.
3. Store model files on the GPU node's local SSD.
4. Import or build the Flashcutter workflow files:

```text
workflows/ai_clone/image_clone_video_v1/workflow_api.json
workflows/ai_clone/video_clone_clip_v1/workflow_api.json
```

5. Verify ComfyUI health from the CPU node:

```bash
curl http://gpu-private-ip:18188/
```

6. Configure the CPU node backend:

```text
FLASHCUTTER_AI_CLONE_PROVIDER=comfyui
FLASHCUTTER_COMFYUI_BASE_URL=http://gpu-private-ip:18188
```

Prefer private-network access between the CPU and GPU nodes. If a public GPU
endpoint must be used temporarily, restrict the security group to the CPU node's
public IP and add an API key or reverse-proxy auth before exposing it.

The detailed ComfyUI workflow build plan lives in:

```text
docs/ai_clone_comfyui_workflow_build.md
```

Provider status can be checked after the backend starts:

```bash
curl https://your-api.example.com/api/ai-clone/provider-status
```

## Deployment Smoke

After deploying, verify the public backend:

```bash
FLASHCUTTER_SMOKE_API_BASE=https://your-api.example.com \
FLASHCUTTER_SMOKE_PHONE="+15551234567" \
FLASHCUTTER_SMOKE_PASSWORD="replace-with-strong-password" \
scripts/deploy_smoke.sh
```

To also verify upload, segmentation, task creation, and render-plan creation,
provide a small local MP4:

```bash
FLASHCUTTER_SMOKE_API_BASE=https://your-api.example.com \
FLASHCUTTER_SMOKE_PHONE="+15551234567" \
FLASHCUTTER_SMOKE_PASSWORD="replace-with-strong-password" \
FLASHCUTTER_SMOKE_VIDEO=/path/to/smoke.mp4 \
scripts/deploy_smoke.sh
```

To include FFmpeg rendering and an output review update:

```bash
FLASHCUTTER_SMOKE_API_BASE=https://your-api.example.com \
FLASHCUTTER_SMOKE_PHONE="+15551234567" \
FLASHCUTTER_SMOKE_PASSWORD="replace-with-strong-password" \
FLASHCUTTER_SMOKE_VIDEO=/path/to/smoke.mp4 \
FLASHCUTTER_SMOKE_RENDER=true \
scripts/deploy_smoke.sh
```

To run a specific template:

```bash
FLASHCUTTER_SMOKE_TEMPLATE_NAME=prod_square_social_proof \
scripts/deploy_smoke.sh
```

For AICF, verify the provider status first, then create a small AI Clone job from
the dashboard. Use a small reference image or a short reference clip while the
GPU workflow is being tested.

## Public Cloud Notes

For the first partner trial, prefer a deployment shape with two services:

- `flashcutter-api`: backend container with a persistent disk or managed volume.
- `flashcutter-web`: frontend container or static hosting.
- `flashcutter-aicf-gpu`: separate GPU node running ComfyUI for AI Clone tests.

Set `FLASHCUTTER_CORS_ORIGINS` to the public frontend origin and build the
frontend with `VITE_API_BASE_URL` pointing to the public backend origin.

For controlled trials, create the partner account first, then redeploy with:

```text
FLASHCUTTER_ALLOW_REGISTRATION=false
```

Keep `FLASHCUTTER_REQUIRE_AUTH=true` for any public-cloud trial environment.

## Information Needed Before Cloud Deployment

When the UCloud resources are available, collect:

```text
CPU node public IP
CPU node private IP
GPU node private IP
GPU node public IP, if private networking is unavailable
Frontend domain
Backend API domain
SSH username and access method
Persistent disk mount path on the CPU node
GPU model and GPU memory
Security group rules
Whether HTTPS will be terminated by Nginx, cloud load balancer, or another proxy
```

Required ports:

```text
80/443 public -> frontend/API proxy
22 restricted -> SSH administration
8000 private/local -> backend container, if Nginx proxies to it
8080 private/local -> frontend container, if not using static hosting
18188 private CPU->GPU only -> ComfyUI
```

Do not expose SQLite files, `/data/storage`, or ComfyUI directly to the public
internet.

## Trial Limitations

- SQLite is acceptable for controlled trial usage but not a multi-worker
  production backend.
- Phone/password login and in-memory sessions are acceptable for controlled
  trials only. Replace them with durable server-side sessions before broad
  public access or multi-instance deployment.
- Object storage, durable workers, migrations, and role-based approval history
  remain production replacement points.
- The GPU node is an experimental AICF worker during the first trial. Generated
  clips should be manually checked before they are used in production templates.
