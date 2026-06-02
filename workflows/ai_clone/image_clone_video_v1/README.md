# image_clone_video_v1

Goal: use one rights-cleared reference image and a prompt to produce a short
vertical video clip suitable for Flashcutter's video clip library.

Expected output:

- MP4 video.
- 1080x1920 preferred.
- 2-8 seconds.
- No visible watermark.
- Safe to reuse in ad variant templates.

Resource checklist:

- Base image/video model.
- Motion module or image-to-video node chain.
- Reference-image conditioning node.
- Tested `workflow_api.json` exported from ComfyUI.
- One smoke-test input image and expected output.
