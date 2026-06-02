# AI Clone ComfyUI Workflows

Flashcutter owns the workflow integration layer here. Operators should not edit
node graphs inside the product UI. We keep the ComfyUI API workflow JSON,
resource notes, and Flashcutter parameter bindings in this directory.

## Workflows

- `image_clone_video_v1`: reference image + prompt -> short vertical MP4.
- `video_clone_clip_v1`: reference video + prompt -> short vertical MP4.

## Required Resources From Operator

Provide these files or links before enabling the real provider:

- ComfyUI API workflow JSON exported from the tested graph.
- Model checkpoints and download source.
- LoRA / ControlNet / IP-Adapter / AnimateDiff resources, if used.
- Custom node list and install source.
- A small reference image and video for smoke tests.
- Expected output examples for style comparison.

## Backend Binding Contract

The backend injects these values into the workflow by path:

```json
{
  "prompt": ["6", "inputs", "text"],
  "negative_prompt": ["7", "inputs", "text"],
  "reference_file": ["10", "inputs", "image"]
}
```

If the real workflow uses different node ids, update the `bindings` field in
the corresponding `manifest.json` and set the workflow path in `.env`.
