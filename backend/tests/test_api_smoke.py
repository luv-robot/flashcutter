import io
import zipfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


def unique_phone() -> str:
    return f"+1555{uuid4().int % 10_000_0000:08d}"


def recipe_json(
    *,
    title: str = "Test recipe",
    clip_duration: float = 3,
    max_clip_count: int = 2,
    target_duration: Optional[float] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    fps: Optional[float] = None,
    fit: str = "original",
    transformations: Optional[dict] = None,
    music: Optional[dict] = None,
) -> dict:
    delivery = {
        "aspect_ratio": "source" if width is None or height is None else "custom",
        "format": "mp4",
        "fit": fit,
    }
    if width is not None and height is not None:
        delivery.update({"width": width, "height": height})
    if fps is not None:
        delivery["fps"] = fps
    return {
        "schema_version": 2,
        "type": "variant_recipe",
        "recipe_id": f"test.{uuid4().hex}",
        "name": title,
        "blueprint": {
            "blueprint_id": "test_blueprint_v1",
            "name": title,
            "creative_goal": {"title": title},
            "production_contract": {
                "use_case": "Test recipe for rights-cleared source footage.",
                "operator_notes": "Test fixture.",
                "review_checklist": ["Review the generated variant."],
            },
            "editing": {
                "cut_style": "fixed_interval",
                "clip_duration_seconds": clip_duration,
                "target_duration_seconds": target_duration,
                "max_clip_count": max_clip_count,
            },
            "slots": [{"slot": "hook", "role": "source_segment"}],
        },
        "render_preset": {
            "preset_id": "test_preset",
            "name": "Test preset",
            "delivery": delivery,
        },
        "style_pack": {
            "style_pack_id": "test_style",
            "name": "Test style",
            "transformations": transformations or {},
        },
        "music": music or {"mode": "replace", "loop": True},
        "review_notes": "Check visible changes.",
    }


def test_api_smoke_path(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 6.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        first = output_dir / "0001.mp4"
        second = output_dir / "0002.mp4"
        first.write_bytes(b"segment-1")
        second.write_bytes(b"segment-2")
        return [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": 3.0,
                "duration_seconds": 3.0,
                "file_path": str(first),
            },
            {
                "index": 1,
                "start_time": 3.0,
                "end_time": 6.0,
                "duration_seconds": 3.0,
                "file_path": str(second),
            },
        ]

    def fake_render_concat(segment_paths, concat_file, output_path):
        output_path.write_bytes(b"output-video")

    def fake_render_timeline(
        segment_paths,
        concat_file,
        output_path,
        width=None,
        height=None,
        fps=None,
        fit="original",
        transformations=None,
    ):
        output_path.write_bytes(b"output-video")

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_concat", fake_render_concat)
    monkeypatch.setattr(routes, "render_timeline", fake_render_timeline)

    with TestClient(app) as client:
        templates_response = client.get("/api/templates")
        assert templates_response.status_code == 200
        template_id = templates_response.json()[0]["id"]

        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("sample.mp4", b"fake-video", "video/mp4")},
        )
        assert upload_response.status_code == 200
        asset_id = upload_response.json()["id"]

        segment_response = client.post(f"/api/assets/{asset_id}/segment")
        assert segment_response.status_code == 200
        assert len(segment_response.json()) == 2

        task_response = client.post(
            "/api/tasks",
            json={
                "name": "api-smoke",
                "asset_id": asset_id,
                "template_id": template_id,
                "params_json": {},
            },
        )
        assert task_response.status_code == 200
        task_id = task_response.json()["id"]

        plan_response = client.post(f"/api/tasks/{task_id}/render-plan")
        assert plan_response.status_code == 200
        assert len(plan_response.json()["plan_json"]["clips"]) >= 1

        render_response = client.post(f"/api/tasks/{task_id}/render")
        assert render_response.status_code == 200
        assert render_response.json()["status"] == "ready"


def test_run_task_pipeline(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 6.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        first = output_dir / "0001.mp4"
        second = output_dir / "0002.mp4"
        first.write_bytes(b"segment-1")
        second.write_bytes(b"segment-2")
        return [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": segment_seconds,
                "duration_seconds": segment_seconds,
                "file_path": str(first),
            },
            {
                "index": 1,
                "start_time": segment_seconds,
                "end_time": segment_seconds * 2,
                "duration_seconds": segment_seconds,
                "file_path": str(second),
            },
        ]

    def fake_render_concat(segment_paths, concat_file, output_path):
        output_path.write_bytes(b"output-video")

    def fake_render_timeline(
        segment_paths,
        concat_file,
        output_path,
        width=None,
        height=None,
        fps=None,
        fit="original",
        transformations=None,
    ):
        output_path.write_bytes(b"output-video")

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_concat", fake_render_concat)
    monkeypatch.setattr(routes, "render_timeline", fake_render_timeline)

    with TestClient(app) as client:
        template_id = client.get("/api/templates").json()[0]["id"]
        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("sample.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]
        task_response = client.post(
            "/api/tasks",
            json={
                "name": "pipeline-smoke",
                "asset_id": asset_id,
                "template_id": template_id,
                "params_json": {},
            },
        )
        task_id = task_response.json()["id"]

        run_response = client.post(
            f"/api/tasks/{task_id}/run",
            json={"segment_seconds": 2.0},
        )

    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["task"]["status"] == "completed"
    assert len(payload["segments"]) == 2
    assert payload["render_plan"]["status"] == "rendered"
    assert payload["output"]["status"] == "ready"

    with TestClient(app) as client:
        events_response = client.get(f"/api/tasks/{payload['task']['id']}/events")
    assert events_response.status_code == 200
    events = events_response.json()
    assert any(event["status"] == "segmenting" for event in events)
    assert any(event["status"] == "completed" for event in events)


def test_import_asset_url(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self):
            self.chunks = [b"remote-video", b""]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self, size):
            return self.chunks.pop(0)

    def fake_urlopen(request, timeout):
        return FakeResponse()

    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 5.0,
            "width": 640,
            "height": 360,
            "fps": 24.0,
        }

    monkeypatch.setattr(routes, "urlopen", fake_urlopen)
    monkeypatch.setattr(routes, "probe_media", fake_probe_media)

    with TestClient(app) as client:
        response = client.post(
            "/api/assets/import-url",
            json={"url": "https://example.test/video.mp4"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["original_filename"] == "video.mp4"
    assert payload["status"] == "ready"


def test_detect_text_regions_for_asset(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 5.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        }

    def fake_detect_text_regions(source_path, output_dir, width, height, duration_seconds):
        return [
            {
                "x": 60,
                "y": 1500,
                "width": 960,
                "height": 220,
                "confidence": 0.72,
                "source": "test",
                "text": "old caption",
            }
        ]

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "detect_text_regions", fake_detect_text_regions)

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("text-source.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]
        response = client.post(f"/api/assets/{asset_id}/text-regions/detect")

    assert response.status_code == 200
    payload = response.json()
    assert payload["regions"][0]["text"] == "old caption"
    assert payload["cover_regions"][0]["color"] == "black@0.84"


def test_variant_preflight_summarizes_visible_changes(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 9.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("preflight-source.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]
        template_response = client.post(
            "/api/templates",
            json={
                "name": f"preflight-template-{uuid4().hex}",
                "version": 1,
                "json_spec": recipe_json(
                    title="Preflight",
                    clip_duration=3,
                    max_clip_count=2,
                    width=1080,
                    height=1920,
                    fps=30,
                    fit="cover",
                    transformations={
                        "playback_speed": 1.2,
                        "cover_regions": [
                            {"x": 10, "y": 10, "width": 100, "height": 40}
                        ],
                        "text_overlays": [
                            {"text": "NEW", "x": 20, "y": 20}
                        ],
                    },
                ),
            },
        )
        template_id = template_response.json()["id"]
        response = client.post(
            f"/api/assets/{asset_id}/render-variants/preflight",
            json={
                "name_prefix": "preflight",
                "template_ids": [template_id],
                "params_json": {},
            },
        )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["estimated_clip_count"] == 2
    assert item["output_width"] == 1080
    assert item["cover_region_count"] == 1
    assert item["text_overlay_count"] == 1


def test_template_crud() -> None:
    template_name = f"template-crud-test-{uuid4().hex}"
    template_payload = {
        "name": template_name,
        "description": "Created by test",
        "version": 1,
        "json_spec": recipe_json(
            title="Template CRUD",
            clip_duration=2.5,
            max_clip_count=2,
            width=1080,
            height=1920,
            fps=30,
            fit="original",
        ),
        "is_builtin": False,
    }

    with TestClient(app) as client:
        create_response = client.post("/api/templates", json=template_payload)
        assert create_response.status_code == 200
        template = create_response.json()

        get_response = client.get(f"/api/templates/{template['id']}")
        assert get_response.status_code == 200
        assert (
            get_response.json()["json_spec"]["blueprint"]["editing"]["max_clip_count"]
            == 2
        )

        update_response = client.put(
            f"/api/templates/{template['id']}",
            json={"description": "Updated by test", "version": 2},
        )
        assert update_response.status_code == 200
        assert update_response.json()["version"] == 2

        delete_response = client.delete(f"/api/templates/{template['id']}")
        assert delete_response.status_code == 204


def test_builtin_templates_cannot_be_updated_or_deleted() -> None:
    with TestClient(app) as client:
        template = next(
            item for item in client.get("/api/templates").json() if item["is_builtin"]
        )

        update_response = client.put(
            f"/api/templates/{template['id']}",
            json={"description": "Should not be allowed"},
        )
        assert update_response.status_code == 400

        delete_response = client.delete(f"/api/templates/{template['id']}")
        assert delete_response.status_code == 400


def test_template_validation_endpoint() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/templates/validate",
            json={
                "json_spec": recipe_json(
                    title="Validate",
                    clip_duration=2,
                    max_clip_count=3,
                    width=1080,
                    height=1920,
                    fps=30,
                    fit="cover",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["normalized_spec"]["output"]["width"] == 1080
    assert payload["normalized_spec"]["layout"]["fit"] == "cover"


def test_template_validation_rejects_bad_fit() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/templates/validate",
            json={
                "json_spec": recipe_json(
                    width=1080,
                    height=1920,
                    fit="stretch",
                )
            },
        )

    assert response.status_code == 422


def test_template_validation_rejects_odd_dimensions() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/templates/validate",
            json={
                "json_spec": recipe_json(
                    width=1079,
                    height=1920,
                )
            },
        )

    assert response.status_code == 422


def test_template_drives_render_plan_selection(monkeypatch) -> None:
    template_name = f"first-two-template-{uuid4().hex}"

    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 9.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        segments = []
        for index in range(3):
            path = output_dir / f"{index + 1:04d}.mp4"
            path.write_bytes(f"segment-{index + 1}".encode())
            start = index * segment_seconds
            segments.append(
                {
                    "index": index,
                    "start_time": start,
                    "end_time": start + segment_seconds,
                    "duration_seconds": segment_seconds,
                    "file_path": str(path),
                }
            )
        return segments

    def fake_render_concat(segment_paths, concat_file, output_path):
        output_path.write_bytes(b"output-video")

    def fake_render_timeline(
        segment_paths,
        concat_file,
        output_path,
        width=None,
        height=None,
        fps=None,
        fit="original",
        transformations=None,
    ):
        output_path.write_bytes(b"output-video")

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_concat", fake_render_concat)
    monkeypatch.setattr(routes, "render_timeline", fake_render_timeline)

    with TestClient(app) as client:
        template_response = client.post(
            "/api/templates",
            json={
                "name": template_name,
                "version": 1,
                "json_spec": recipe_json(
                    title="First two",
                    clip_duration=3,
                    max_clip_count=2,
                    target_duration=6,
                    width=1080,
                    height=1920,
                    fps=30,
                    fit="original",
                ),
            },
        )
        assert template_response.status_code == 200
        template_id = template_response.json()["id"]

        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("sample.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]

        task_response = client.post(
            "/api/tasks",
            json={
                "name": "template-driven",
                "asset_id": asset_id,
                "template_id": template_id,
                "params_json": {},
            },
        )
        task_id = task_response.json()["id"]

        run_response = client.post(f"/api/tasks/{task_id}/run", json={})

    assert run_response.status_code == 200
    render_plan = run_response.json()["render_plan"]["plan_json"]
    assert len(render_plan["clips"]) == 2
    assert render_plan["output"]["width"] == 1080
    assert render_plan["output"]["height"] == 1920
    assert render_plan["layout"]["fit"] == "original"


def test_operator_template_fields_drive_render_plan(monkeypatch) -> None:
    template_name = f"operator-template-{uuid4().hex}"

    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 12.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        segments = []
        for index in range(4):
            path = output_dir / f"{index + 1:04d}.mp4"
            path.write_bytes(f"segment-{index + 1}".encode())
            start = index * segment_seconds
            segments.append(
                {
                    "index": index,
                    "start_time": start,
                    "end_time": start + segment_seconds,
                    "duration_seconds": segment_seconds,
                    "file_path": str(path),
                }
            )
        return segments

    def fake_render_concat(segment_paths, concat_file, output_path):
        output_path.write_bytes(b"output-video")

    def fake_render_timeline(
        segment_paths,
        concat_file,
        output_path,
        width=None,
        height=None,
        fps=None,
        fit="original",
        transformations=None,
    ):
        output_path.write_bytes(b"output-video")

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_concat", fake_render_concat)
    monkeypatch.setattr(routes, "render_timeline", fake_render_timeline)

    with TestClient(app) as client:
        template_response = client.post(
            "/api/templates",
            json={
                "name": template_name,
                "version": 1,
                "json_spec": recipe_json(
                    title="New user acquisition cutdown",
                    clip_duration=2,
                    max_clip_count=3,
                    target_duration=6,
                    width=1080,
                    height=1920,
                    fps=30,
                    fit="original",
                ),
            },
        )
        assert template_response.status_code == 200
        template_id = template_response.json()["id"]

        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("sample.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]
        task_response = client.post(
            "/api/tasks",
            json={
                "name": "operator-template-driven",
                "asset_id": asset_id,
                "template_id": template_id,
                "params_json": {},
            },
        )
        task_id = task_response.json()["id"]

        run_response = client.post(f"/api/tasks/{task_id}/run", json={})

    assert run_response.status_code == 200
    render_plan = run_response.json()["render_plan"]["plan_json"]
    assert len(render_plan["clips"]) == 3
    assert render_plan["clips"][0]["duration_seconds"] == 2
    assert render_plan["output"]["width"] == 1080
    assert render_plan["output"]["height"] == 1920
    assert render_plan["selection"]["count"] == 3


def test_batch_tasks_for_one_asset_many_templates(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 6.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("sample.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]

        template_ids = []
        for label in ("short", "long"):
            response = client.post(
                "/api/templates",
                json={
                    "name": f"batch-{label}-{uuid4().hex}",
                    "version": 1,
                    "json_spec": recipe_json(
                        title=f"Batch {label}",
                        clip_duration=3,
                        max_clip_count=1 if label == "short" else 2,
                    ),
                },
            )
            assert response.status_code == 200
            template_ids.append(response.json()["id"])

        batch_response = client.post(
            "/api/tasks/batch",
            json={
                "name_prefix": "seed-video-variant",
                "asset_id": asset_id,
                "template_ids": template_ids,
                "params_json": {},
            },
        )

    assert batch_response.status_code == 200
    tasks = batch_response.json()
    assert len(tasks) == 2
    assert {task["template_id"] for task in tasks} == set(template_ids)
    assert all("seed-video-variant" in task["name"] for task in tasks)
    assert all("sample.mp4" in task["name"] for task in tasks)
    assert len({task["production_run_id"] for task in tasks}) == 1
    assert tasks[0]["production_run_id"] is not None
    assert {task["revision_number"] for task in tasks} == {1}

    revision_response = client.post(
        "/api/tasks/batch",
        json={
            "name_prefix": "seed-video-variant-rework",
            "asset_id": asset_id,
            "template_ids": template_ids[:1],
            "production_run_id": tasks[0]["production_run_id"],
            "params_json": {},
        },
    )
    assert revision_response.status_code == 200
    revision_tasks = revision_response.json()
    assert revision_tasks[0]["production_run_id"] == tasks[0]["production_run_id"]
    assert revision_tasks[0]["revision_number"] == 2

    events_response = client.get(f"/api/tasks/{tasks[0]['id']}/events")
    assert events_response.status_code == 200
    assert events_response.json()[0]["message"] == "Task created"


def test_ai_asset_slot_binding_enters_preflight_and_render_plan(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 3.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        segment_path = output_dir / "0001.mp4"
        segment_path.write_bytes(b"segment")
        return [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": 3.0,
                "duration_seconds": 3.0,
                "file_path": str(segment_path),
            }
        ]

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)

    recipe = recipe_json(title="AI hook recipe", clip_duration=3, max_clip_count=1)
    recipe["slot_bindings"] = {
        "hook": {
            "source_type": "ai_asset",
            "asset_type": "hook",
            "tags": ["cat", "funny"],
            "duration": [2, 4],
            "optional": False,
        }
    }

    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
            },
        )
        headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}
        ai_asset_response = client.post(
            "/api/ai-assets/upload",
            data={
                "title": "Cat hook",
                "asset_type": "hook",
                "provider": "mock",
                "tags": "cat,funny",
            },
            files={"file": ("cat-hook.mp4", b"fake-ai-video", "video/mp4")},
            headers=headers,
        )
        assert ai_asset_response.status_code == 200
        ai_asset_id = ai_asset_response.json()["id"]

        source_response = client.post(
            "/api/assets/upload",
            files={"file": ("source.mp4", b"fake-source-video", "video/mp4")},
            headers=headers,
        )
        asset_id = source_response.json()["id"]
        template_response = client.post(
            "/api/templates",
            json={
                "name": f"ai-slot-{uuid4().hex}",
                "version": 1,
                "json_spec": recipe,
            },
            headers=headers,
        )
        template_id = template_response.json()["id"]

        preflight_response = client.post(
            f"/api/assets/{asset_id}/render-variants/preflight",
            json={
                "name_prefix": "ai-slot",
                "template_ids": [template_id],
                "params_json": {},
            },
            headers=headers,
        )
        assert preflight_response.status_code == 200
        preflight_item = preflight_response.json()["items"][0]
        assert preflight_item["ai_asset_slot_count"] == 1
        assert preflight_item["selected_ai_asset_count"] == 1
        assert preflight_item["warnings"] == []

        task_response = client.post(
            "/api/tasks",
            json={
                "name": "ai-slot-render-plan",
                "asset_id": asset_id,
                "template_id": template_id,
                "params_json": {},
            },
            headers=headers,
        )
        task_id = task_response.json()["id"]
        client.post(f"/api/assets/{asset_id}/segment", headers=headers)
        plan_response = client.post(f"/api/tasks/{task_id}/render-plan", headers=headers)

    assert plan_response.status_code == 200
    plan = plan_response.json()["plan_json"]
    assert plan["ai_asset_slots"][0]["asset_id"] == ai_asset_id
    assert plan["clips"][0]["source_type"] == "ai_asset"
    assert plan["clips"][0]["asset_id"] == ai_asset_id


def test_strong_opening_expansion_suggests_preflights_and_enqueues(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 12.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        }

    enqueued_task_ids = []

    def fake_enqueue(task_id, runner):
        enqueued_task_ids.append(task_id)

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes.task_queue, "enqueue", fake_enqueue)

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("strong-opening-source.mp4", b"fake-video", "video/mp4")},
        )
        assert upload_response.status_code == 200
        asset_id = upload_response.json()["id"]

        suggestion_response = client.post(
            "/api/expansion-plans/strong-opening/copy-suggestions",
            json={
                "asset_id": asset_id,
                "target_count": 5,
                "intensity": "balanced",
                "product_name": "FlashCutter",
                "selling_points": ["前三秒更清楚", "低成本扩量"],
                "forbidden_terms": ["免费"],
            },
        )
        assert suggestion_response.status_code == 200
        suggestions = suggestion_response.json()["suggestions"]
        assert len(suggestions) == 5
        assert all("免费" not in suggestion["text"] for suggestion in suggestions)

        opening_texts = [suggestion["text"] for suggestion in suggestions[:3]]
        expansion_payload = {
            "asset_id": asset_id,
            "target_count": 3,
            "intensity": "balanced",
            "opening_texts": opening_texts,
            "output_preset_id": "vertical_9_16_cover",
            "name_prefix": "strong-opening-test",
        }
        preflight_response = client.post(
            "/api/expansion-runs/strong-opening/preflight",
            json=expansion_payload,
        )
        assert preflight_response.status_code == 200
        preflight = preflight_response.json()
        assert preflight["summary"]["task_count"] == 3
        assert preflight["summary"]["blocked_count"] == 0
        assert preflight["suggestions"][0]["source"] == "user"
        assert "强开场 #1" in preflight["items"][0]["title"]

        enqueue_response = client.post(
            "/api/expansion-runs/strong-opening/enqueue",
            json={
                **expansion_payload,
                "preflight_token": preflight["preflight_token"],
            },
        )

    assert enqueue_response.status_code == 200
    tasks = enqueue_response.json()
    assert len(tasks) == 3
    assert enqueued_task_ids == [task["id"] for task in tasks]
    assert [task["params_json"]["runtime_values"]["opening_hook_text"] for task in tasks] == opening_texts
    assert tasks[0]["params_json"]["expansion"]["plan_id"] == "strong_opening"


def test_output_review_workflow(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 6.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        first = output_dir / "0001.mp4"
        second = output_dir / "0002.mp4"
        first.write_bytes(b"segment-1")
        second.write_bytes(b"segment-2")
        return [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": 3.0,
                "duration_seconds": 3.0,
                "file_path": str(first),
            },
            {
                "index": 1,
                "start_time": 3.0,
                "end_time": 6.0,
                "duration_seconds": 3.0,
                "file_path": str(second),
            },
        ]

    def fake_render_concat(segment_paths, concat_file, output_path):
        output_path.write_bytes(b"output-video")

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_concat", fake_render_concat)

    with TestClient(app) as client:
        template_id = client.get("/api/templates").json()[0]["id"]
        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("review-source.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]
        task_response = client.post(
            "/api/tasks",
            json={
                "name": "review-output",
                "asset_id": asset_id,
                "template_id": template_id,
                "params_json": {},
            },
        )
        task_id = task_response.json()["id"]
        run_response = client.post(f"/api/tasks/{task_id}/run", json={})
        assert run_response.status_code == 200
        output_id = run_response.json()["output"]["id"]
        assert run_response.json()["output"]["review_status"] == "pending_review"

        review_response = client.patch(
            f"/api/outputs/{output_id}/review",
            json={
                "review_status": "approved",
                "review_notes": "Ready for ad testing.",
                "reviewer_name": "Ada",
                "priority": "high",
                "change_requests": [
                    {
                        "category": "copy",
                        "target": "opening caption",
                        "request": "Make the hook more direct.",
                        "priority": "high",
                    }
                ],
                "tags": ["hook", "approved"],
            },
        )
        assert review_response.status_code == 200
        reviewed = review_response.json()
        assert reviewed["review_status"] == "approved"
        assert reviewed["review_notes"] == "Ready for ad testing."
        assert reviewed["review_feedback"]["reviewer_name"] == "Ada"
        assert reviewed["review_feedback"]["priority"] == "high"
        assert reviewed["review_feedback"]["change_requests"][0]["category"] == "copy"
        assert (
            reviewed["review_feedback"]["change_requests"][0]["request"]
            == "Make the hook more direct."
        )
        assert reviewed["production_run_status"] is None
        assert reviewed["reviewed_at"] is not None
        assert reviewed["asset_id"] == asset_id
        assert reviewed["template_id"] == template_id

        asset_outputs_response = client.get(f"/api/assets/{asset_id}/outputs")
        assert asset_outputs_response.status_code == 200
        asset_outputs = asset_outputs_response.json()
        assert any(output["output_id"] == output_id for output in asset_outputs)

        review_list_response = client.get("/api/outputs/review")
        assert review_list_response.status_code == 200
        review_outputs = review_list_response.json()
        assert any(output["output_id"] == output_id for output in review_outputs)


def test_private_music_upload_and_list(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 12.5,
            "width": None,
            "height": None,
            "fps": None,
        }

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)

    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "Music tester",
            },
        )
        assert register_response.status_code == 200
        token = register_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        upload_response = client.post(
            "/api/music/upload",
            data={"title": "Private beat"},
            files={"file": ("beat.mp3", b"fake-audio", "audio/mpeg")},
            headers=headers,
        )
        assert upload_response.status_code == 200
        track = upload_response.json()
        assert track["title"] == "Private beat"
        assert track["scope"] == "private"
        assert track["duration_seconds"] == 12.5

        list_response = client.get("/api/music", headers=headers)
        assert list_response.status_code == 200
        tracks = list_response.json()
        assert any(item["id"] == track["id"] for item in tracks)

        anonymous_list_response = client.get("/api/music")
        assert anonymous_list_response.status_code == 200
        assert all(item["scope"] == "system" for item in anonymous_list_response.json())


def test_ai_asset_video_upload_and_tag_filter(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 2.5,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        }

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)

    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "AI asset tester",
            },
        )
        headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}

        upload_response = client.post(
            "/api/ai-assets/upload",
            data={
                "title": "Surprise hook",
                "asset_type": "hook",
                "prompt": "surprised expression, fast motion",
                "tags": "hook, surprised, cute, hook",
            },
            files={"file": ("hook.mp4", b"fake-video", "video/mp4")},
            headers=headers,
        )

        assert upload_response.status_code == 200
        payload = upload_response.json()
        assert payload["asset_kind"] == "video"
        assert payload["asset_type"] == "hook"
        assert payload["status"] == "ready"
        assert payload["duration_seconds"] == 2.5
        assert [tag["tag"] for tag in payload["tags"]] == ["hook", "surprised", "cute"]

        list_response = client.get("/api/ai-assets?tag=surprised", headers=headers)
        assert list_response.status_code == 200
        assert any(asset["id"] == payload["id"] for asset in list_response.json())


def test_user_uploaded_video_clip_provider_filter(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 4.0,
            "width": 720,
            "height": 1280,
            "fps": 24.0,
        }

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)

    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "Clip uploader",
            },
        )
        headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}

        upload_response = client.post(
            "/api/ai-assets/upload",
            data={
                "title": "Product spin clip",
                "asset_type": "broll",
                "provider": "user_upload",
                "tags": "product,broll",
                "prompt": "Reusable product spin for mid-roll proof.",
            },
            files={"file": ("product-spin.mp4", b"fake-video", "video/mp4")},
            headers=headers,
        )
        assert upload_response.status_code == 200
        asset_id = upload_response.json()["id"]

        filtered_response = client.get(
            "/api/ai-assets?asset_kind=video&provider=user_upload&scope=private",
            headers=headers,
        )
        assert filtered_response.status_code == 200
        assert any(asset["id"] == asset_id for asset in filtered_response.json())


def test_ai_asset_image_upload_and_private_visibility() -> None:
    with TestClient(app) as client:
        owner_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "AI image owner",
            },
        )
        other_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "AI image other",
            },
        )
        owner_headers = {"Authorization": f"Bearer {owner_response.json()['access_token']}"}
        other_headers = {"Authorization": f"Bearer {other_response.json()['access_token']}"}

        upload_response = client.post(
            "/api/ai-assets/upload",
            data={"title": "Reference frame", "asset_type": "broll", "tags": "product"},
            files={"file": ("frame.png", b"fake-image", "image/png")},
            headers=owner_headers,
        )

        assert upload_response.status_code == 200
        payload = upload_response.json()
        assert payload["asset_kind"] == "image"
        assert payload["status"] == "ready"
        assert payload["duration_seconds"] is None

        owner_list = client.get("/api/ai-assets?asset_kind=image", headers=owner_headers)
        assert owner_list.status_code == 200
        assert any(asset["id"] == payload["id"] for asset in owner_list.json())

        other_get = client.get(f"/api/ai-assets/{payload['id']}", headers=other_headers)
        assert other_get.status_code == 404


def test_local_motion_ai_asset_generation(monkeypatch) -> None:
    def fake_render_image_motion_clip(
        image_path,
        output_path,
        duration_seconds,
        width=1080,
        height=1920,
        fps=30.0,
    ):
        assert image_path.exists()
        assert duration_seconds == 3.0
        output_path.write_bytes(b"generated-video")

    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 3.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        }

    monkeypatch.setattr(routes, "render_image_motion_clip", fake_render_image_motion_clip)
    monkeypatch.setattr(routes, "probe_media", fake_probe_media)

    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "AI generator",
            },
        )
        headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}

        response = client.post(
            "/api/ai-assets/generate/local-motion",
            data={
                "title": "Generated hook",
                "asset_type": "hook",
                "prompt": "turn this reference image into a short opening hook",
                "tags": "hook,generated",
                "duration_seconds": "3",
            },
            files={"file": ("reference.png", b"fake-image", "image/png")},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local_motion_mvp"
    assert payload["asset_kind"] == "video"
    assert payload["status"] == "ready"
    assert payload["source_image_path"]
    assert payload["duration_seconds"] == 3.0
    assert [tag["tag"] for tag in payload["tags"]] == ["hook", "generated"]


def test_system_ai_asset_visible_to_other_users(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 4.0,
            "width": 1280,
            "height": 720,
            "fps": 24.0,
        }

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)

    with TestClient(app) as client:
        creator_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "System clip creator",
            },
        )
        viewer_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "System clip viewer",
            },
        )
        creator_headers = {"Authorization": f"Bearer {creator_response.json()['access_token']}"}
        viewer_headers = {"Authorization": f"Bearer {viewer_response.json()['access_token']}"}

        upload_response = client.post(
            "/api/ai-assets/upload",
            data={
                "title": "Shared CTA",
                "asset_type": "cta",
                "scope": "system",
                "tags": "cta,hard_sell",
            },
            files={"file": ("shared-cta.mp4", b"fake-video", "video/mp4")},
            headers=creator_headers,
        )

        assert upload_response.status_code == 200
        asset_id = upload_response.json()["id"]
        viewer_list = client.get("/api/ai-assets?scope=system", headers=viewer_headers)
        assert viewer_list.status_code == 200
        assert any(asset["id"] == asset_id for asset in viewer_list.json())

        update_response = client.patch(
            f"/api/ai-assets/{asset_id}",
            json={"title": "Cannot edit"},
            headers=viewer_headers,
        )
        assert update_response.status_code == 403


def test_render_variants_for_asset(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 6.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        first = output_dir / "0001.mp4"
        second = output_dir / "0002.mp4"
        first.write_bytes(b"segment-1")
        second.write_bytes(b"segment-2")
        return [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": 3.0,
                "duration_seconds": 3.0,
                "file_path": str(first),
            },
            {
                "index": 1,
                "start_time": 3.0,
                "end_time": 6.0,
                "duration_seconds": 3.0,
                "file_path": str(second),
            },
        ]

    def fake_render_concat(segment_paths, concat_file, output_path):
        output_path.write_bytes(b"output-video")

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_concat", fake_render_concat)

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("variant-source.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]
        template_ids = []
        for label, count in (("hook", 1), ("proof", 2)):
            response = client.post(
                "/api/templates",
                json={
                    "name": f"render-variant-{label}-{uuid4().hex}",
                    "version": 1,
                    "json_spec": recipe_json(
                        title=f"Render variant {label}",
                        clip_duration=3,
                        max_clip_count=count,
                    ),
                },
            )
            assert response.status_code == 200
            template_ids.append(response.json()["id"])

        render_response = client.post(
            f"/api/assets/{asset_id}/render-variants",
            json={
                "name_prefix": "campaign",
                "template_ids": template_ids,
                "params_json": {},
            },
        )

    assert render_response.status_code == 200
    outputs = render_response.json()
    assert len(outputs) == 2
    assert {output["template_id"] for output in outputs} == set(template_ids)
    assert all(output["review_status"] == "pending_review" for output in outputs)
    assert len({output["production_run_id"] for output in outputs}) == 1
    assert all(output["production_run_name"] for output in outputs)
    assert {output["production_run_status"] for output in outputs} == {"in_review"}
    production_run_id = outputs[0]["production_run_id"]

    approve_response = client.patch(
        f"/api/outputs/{outputs[0]['output_id']}/review",
        json={"review_status": "approved", "review_notes": "Package this output."},
    )
    assert approve_response.status_code == 200

    estimate_response = client.get(
        f"/api/production-runs/{production_run_id}/package/estimate"
    )
    assert estimate_response.status_code == 200
    estimate = estimate_response.json()
    assert estimate["approved_output_count"] == 1
    assert estimate["total_size_bytes"] > 0

    package_response = client.get(f"/api/production-runs/{production_run_id}/package")
    assert package_response.status_code == 200
    assert package_response.headers["content-type"] == "application/zip"
    assert package_response.content.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(package_response.content)) as archive:
        names = set(archive.namelist())
        assert "metadata/manifest.json" in names
        assert "metadata/review_records.csv" in names
        manifest = archive.read("metadata/manifest.json").decode("utf-8")
        assert "Only approved videos are included" in manifest
        review_records = archive.read("metadata/review_records.csv").decode("utf-8")
        assert "Package this output." in review_records

    run_status_response = client.patch(
        f"/api/production-runs/{production_run_id}/status",
        json={"status": "needs_revision"},
    )
    assert run_status_response.status_code == 200
    assert run_status_response.json()["status"] == "needs_revision"


def test_generated_outputs_are_scoped_to_owner(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 6.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        segment = output_dir / "0001.mp4"
        segment.write_bytes(b"segment-1")
        return [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": 3.0,
                "duration_seconds": 3.0,
                "file_path": str(segment),
            }
        ]

    def fake_render_timeline(
        segment_paths,
        concat_file,
        output_path,
        width=None,
        height=None,
        fps=None,
        fit="original",
        transformations=None,
    ):
        output_path.write_bytes(b"owner-output-video")

    def fake_render_concat(segment_paths, concat_file, output_path):
        output_path.write_bytes(b"owner-output-video")

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_concat", fake_render_concat)
    monkeypatch.setattr(routes, "render_timeline", fake_render_timeline)

    with TestClient(app) as client:
        owner_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "Owner",
            },
        )
        other_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "Other",
            },
        )
        owner_token = owner_response.json()["access_token"]
        other_token = other_response.json()["access_token"]
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        other_headers = {"Authorization": f"Bearer {other_token}"}

        template_id = client.get("/api/templates", headers=owner_headers).json()[0]["id"]
        upload_response = client.post(
            "/api/assets/upload",
            headers=owner_headers,
            files={"file": ("owner-source.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]

        render_response = client.post(
            f"/api/assets/{asset_id}/render-variants",
            headers=owner_headers,
            json={
                "name_prefix": "owner-only",
                "template_ids": [template_id],
                "params_json": {},
            },
        )
        assert render_response.status_code == 200
        output = render_response.json()[0]
        output_id = output["output_id"]
        task_id = output["task_id"]
        production_run_id = output["production_run_id"]

        approve_response = client.patch(
            f"/api/outputs/{output_id}/review",
            headers=owner_headers,
            json={"review_status": "approved", "review_notes": "Owner approved."},
        )
        assert approve_response.status_code == 200

        assert any(
            item["id"] == task_id
            for item in client.get("/api/tasks", headers=owner_headers).json()
        )
        assert any(
            item["id"] == output_id
            for item in client.get("/api/outputs", headers=owner_headers).json()
        )
        assert client.get(
            f"/api/outputs/{output_id}/file", headers=owner_headers
        ).status_code == 200
        assert client.get(
            f"/api/outputs/{output_id}/file?access_token={owner_token}"
        ).status_code == 200
        assert client.get(
            f"/api/production-runs/{production_run_id}/package/estimate",
            headers=owner_headers,
        ).status_code == 200
        assert client.get(
            f"/api/production-runs/{production_run_id}/package",
            headers=owner_headers,
        ).status_code == 200

        assert all(
            item["id"] != task_id
            for item in client.get("/api/tasks", headers=other_headers).json()
        )
        assert all(
            item["id"] != output_id
            for item in client.get("/api/outputs", headers=other_headers).json()
        )
        assert all(
            item["output_id"] != output_id
            for item in client.get("/api/outputs/review", headers=other_headers).json()
        )
        assert all(
            item["output_id"] != output_id
            for item in client.get(
                f"/api/assets/{asset_id}/outputs", headers=other_headers
            ).json()
        )

        forbidden_requests = [
            ("get", f"/api/tasks/{task_id}/events", None),
            ("post", f"/api/tasks/{task_id}/render-plan", None),
            ("post", f"/api/tasks/{task_id}/render", None),
            ("post", f"/api/tasks/{task_id}/enqueue", None),
            ("post", f"/api/tasks/{task_id}/run", None),
            ("get", f"/api/outputs/{output_id}/file", None),
            (
                "patch",
                f"/api/outputs/{output_id}/review",
                {"review_status": "rejected", "review_notes": "Should not work."},
            ),
            ("get", f"/api/production-runs/{production_run_id}/package/estimate", None),
            ("get", f"/api/production-runs/{production_run_id}/package", None),
            (
                "patch",
                f"/api/production-runs/{production_run_id}/status",
                {"status": "needs_revision"},
            ),
        ]
        for method, path, body in forbidden_requests:
            if body is None:
                response = getattr(client, method)(path, headers=other_headers)
            else:
                response = getattr(client, method)(path, headers=other_headers, json=body)
            assert response.status_code == 404, path

        query_token_response = client.get(
            f"/api/outputs/{output_id}/file?access_token={other_token}"
        )
        assert query_token_response.status_code == 404


def test_template_transformations_are_recorded_and_rendered(monkeypatch) -> None:
    template_name = f"creative-transform-{uuid4().hex}"
    captured_render = {}

    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 6.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        first = output_dir / "0001.mp4"
        second = output_dir / "0002.mp4"
        first.write_bytes(b"segment-1")
        second.write_bytes(b"segment-2")
        return [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": 3.0,
                "duration_seconds": 3.0,
                "file_path": str(first),
            },
            {
                "index": 1,
                "start_time": 3.0,
                "end_time": 6.0,
                "duration_seconds": 3.0,
                "file_path": str(second),
            },
        ]

    def fake_render_timeline(
        segment_paths,
        concat_file,
        output_path,
        width=None,
        height=None,
        fps=None,
        fit="original",
        transformations=None,
    ):
        captured_render["transformations"] = transformations
        captured_render["fit"] = fit
        output_path.write_bytes(b"output-video")

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_timeline", fake_render_timeline)

    with TestClient(app) as client:
        template_response = client.post(
            "/api/templates",
            json={
                "name": template_name,
                "version": 1,
                "json_spec": recipe_json(
                    title="Transform render",
                    clip_duration=3,
                    max_clip_count=2,
                    transformations={
                        "brightness": 0.03,
                        "contrast": 1.08,
                        "saturation": 1.12,
                        "playback_speed": 1.03,
                        "volume": 0.95,
                    },
                ),
            },
        )
        assert template_response.status_code == 200
        template_id = template_response.json()["id"]

        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("source.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]
        task_response = client.post(
            "/api/tasks",
            json={
                "name": "creative-transform",
                "asset_id": asset_id,
                "template_id": template_id,
                "params_json": {},
            },
        )
        task_id = task_response.json()["id"]

        run_response = client.post(f"/api/tasks/{task_id}/run", json={})

    assert run_response.status_code == 200
    render_plan = run_response.json()["render_plan"]["plan_json"]
    assert render_plan["transformations"]["brightness"] == 0.03
    assert render_plan["transformations"]["playback_speed"] == 1.03
    assert captured_render["transformations"]["saturation"] == 1.12
    assert captured_render["fit"] == "original"


def test_template_music_replaces_output_audio(monkeypatch) -> None:
    template_name = f"music-replace-{uuid4().hex}"
    captured_music = {}

    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 6.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        first = output_dir / "0001.mp4"
        second = output_dir / "0002.mp4"
        first.write_bytes(b"segment-1")
        second.write_bytes(b"segment-2")
        return [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": 3.0,
                "duration_seconds": 3.0,
                "file_path": str(first),
            },
            {
                "index": 1,
                "start_time": 3.0,
                "end_time": 6.0,
                "duration_seconds": 3.0,
                "file_path": str(second),
            },
        ]

    def fake_render_concat(segment_paths, concat_file, output_path):
        output_path.write_bytes(b"output-video")

    def fake_replace_audio_track(
        video_path,
        music_path,
        output_path,
        duration_seconds,
        volume=1.0,
        loop=True,
    ):
        captured_music["video_path"] = video_path
        captured_music["music_path"] = music_path
        captured_music["duration_seconds"] = duration_seconds
        captured_music["volume"] = volume
        captured_music["loop"] = loop
        output_path.write_bytes(b"music-output-video")

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_concat", fake_render_concat)
    monkeypatch.setattr(routes, "replace_audio_track", fake_replace_audio_track)

    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "phone": unique_phone(),
                "password": "trial-secret",
                "display_name": "Music render tester",
            },
        )
        headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}

        music_response = client.post(
            "/api/music/upload",
            data={"title": "Render beat"},
            files={"file": ("render-beat.mp3", b"fake-audio", "audio/mpeg")},
            headers=headers,
        )
        track_id = music_response.json()["id"]

        template_response = client.post(
            "/api/templates",
            json={
                "name": template_name,
                "version": 1,
                "json_spec": recipe_json(
                    title="Music render",
                    clip_duration=3,
                    max_clip_count=2,
                    music={
                        "mode": "replace",
                        "track_id": track_id,
                        "volume": 0.8,
                        "loop": True,
                    },
                ),
            },
            headers=headers,
        )
        template_id = template_response.json()["id"]

        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("music-source.mp4", b"fake-video", "video/mp4")},
            headers=headers,
        )
        asset_id = upload_response.json()["id"]
        task_response = client.post(
            "/api/tasks",
            json={
                "name": "music-render",
                "asset_id": asset_id,
                "template_id": template_id,
                "params_json": {},
            },
            headers=headers,
        )
        run_response = client.post(
            f"/api/tasks/{task_response.json()['id']}/run",
            json={},
            headers=headers,
        )

    assert run_response.status_code == 200
    render_plan = run_response.json()["render_plan"]["plan_json"]
    assert render_plan["music"]["track_id"] == track_id
    assert render_plan["music"]["mode"] == "replace"
    assert captured_music["volume"] == 0.8
    assert captured_music["loop"] is True
    assert captured_music["music_path"].name.startswith("music-")


def test_render_output_dimension_mismatch_records_failed_output(monkeypatch) -> None:
    def fake_probe_media(path: Path) -> dict:
        return {
            "duration_seconds": 6.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
        }

    def fake_split_fixed_segments(source_path, output_dir, duration_seconds, segment_seconds):
        first = output_dir / "0001.mp4"
        first.write_bytes(b"segment-1")
        return [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": 3.0,
                "duration_seconds": 3.0,
                "file_path": str(first),
            }
        ]

    def fake_render_timeline(**kwargs):
        kwargs["output_path"].write_bytes(b"x" * 2048)

    monkeypatch.setattr(routes, "probe_media", fake_probe_media)
    monkeypatch.setattr(routes, "split_fixed_segments", fake_split_fixed_segments)
    monkeypatch.setattr(routes, "render_timeline", fake_render_timeline)

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/assets/upload",
            files={"file": ("bad-output-source.mp4", b"fake-video", "video/mp4")},
        )
        asset_id = upload_response.json()["id"]
        template_response = client.post(
            "/api/templates",
            json={
                "name": f"dimension-mismatch-{uuid4().hex}",
                "version": 1,
                "json_spec": recipe_json(
                    title="Dimension mismatch",
                    clip_duration=3,
                    max_clip_count=1,
                    width=1080,
                    height=1920,
                    fps=30,
                    fit="cover",
                ),
            },
        )
        template_id = template_response.json()["id"]
        task_response = client.post(
            "/api/tasks",
            json={
                "name": "dimension-mismatch",
                "asset_id": asset_id,
                "template_id": template_id,
                "params_json": {},
            },
        )
        task_id = task_response.json()["id"]

        run_response = client.post(f"/api/tasks/{task_id}/run", json={})
        outputs_response = client.get("/api/outputs")
        events_response = client.get(f"/api/tasks/{task_id}/events")

    assert run_response.status_code == 500
    assert any(
        output["task_id"] == task_id and output["status"] == "failed"
        for output in outputs_response.json()
    )
    assert any(event["status"] == "failed" for event in events_response.json())
