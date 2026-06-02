# video_clone_clip_v1

Goal: use one rights-cleared source video and a prompt to produce a similar,
short, reusable clip for Flashcutter's video clip library.

Expected output:

- MP4 video.
- 1080x1920 preferred.
- 2-8 seconds.
- Stable subject and camera motion.
- No visible watermark.

Resource checklist:

- Video-to-video workflow or frame-conditioning pipeline.
- Motion/style preservation settings.
- Custom nodes required by the workflow.
- Tested `workflow_api.json` exported from ComfyUI.
- One smoke-test source video and expected output.
