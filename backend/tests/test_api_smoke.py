from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


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
        safe_area_top=0,
        safe_area_bottom=0,
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
        assert len(plan_response.json()["plan_json"]["clips"]) == 2

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
        safe_area_top=0,
        safe_area_bottom=0,
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
                "json_spec": {
                    "type": "concat",
                    "creative_goal": {"title": "Preflight"},
                    "editing": {"clip_duration_seconds": 3, "max_clip_count": 2},
                    "delivery": {
                        "width": 1080,
                        "height": 1920,
                        "fps": 30,
                        "format": "mp4",
                        "fit": "cover",
                    },
                    "transformations": {
                        "playback_speed": 1.2,
                        "cover_regions": [
                            {"x": 10, "y": 10, "width": 100, "height": 40}
                        ],
                        "text_overlays": [
                            {"text": "NEW", "x": 20, "y": 20}
                        ],
                    },
                    "review_notes": "Check visible changes.",
                },
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
        "json_spec": {
            "type": "concat",
            "segments": {"segment_seconds": 2.5},
            "selection": {"mode": "first_n", "count": 2},
            "output": {"width": 1080, "height": 1920, "fps": 30, "format": "mp4"},
            "layout": {"fit": "original"},
        },
        "is_builtin": False,
    }

    with TestClient(app) as client:
        create_response = client.post("/api/templates", json=template_payload)
        assert create_response.status_code == 200
        template = create_response.json()

        get_response = client.get(f"/api/templates/{template['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["json_spec"]["selection"]["count"] == 2

        update_response = client.put(
            f"/api/templates/{template['id']}",
            json={"description": "Updated by test", "version": 2},
        )
        assert update_response.status_code == 200
        assert update_response.json()["version"] == 2

        delete_response = client.delete(f"/api/templates/{template['id']}")
        assert delete_response.status_code == 204


def test_template_validation_endpoint() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/templates/validate",
            json={
                "json_spec": {
                    "type": "concat",
                    "editing": {
                        "clip_duration_seconds": 2,
                        "max_clip_count": 3,
                    },
                    "delivery": {
                        "aspect_ratio": "9:16",
                        "width": 1080,
                        "height": 1920,
                        "fps": 30,
                        "format": "mp4",
                        "fit": "cover",
                    },
                }
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
                "json_spec": {
                    "type": "concat",
                    "delivery": {
                        "width": 1080,
                        "height": 1920,
                        "fit": "stretch",
                    },
                }
            },
        )

    assert response.status_code == 422


def test_template_validation_rejects_odd_dimensions() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/templates/validate",
            json={
                "json_spec": {
                    "type": "concat",
                    "output": {
                        "width": 1079,
                        "height": 1920,
                        "format": "mp4",
                    },
                }
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
        safe_area_top=0,
        safe_area_bottom=0,
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
                "json_spec": {
                    "type": "concat",
                    "segments": {"segment_seconds": 3},
                    "selection": {
                        "mode": "first_n",
                        "count": 2,
                        "max_total_duration": 6,
                    },
                    "output": {"width": 1080, "height": 1920, "fps": 30, "format": "mp4"},
                    "layout": {"fit": "original"},
                },
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
        safe_area_top=0,
        safe_area_bottom=0,
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
                "json_spec": {
                    "type": "concat",
                    "creative_goal": {
                        "title": "New user acquisition cutdown",
                        "audience": "cold traffic",
                        "selling_points": ["fast setup", "human-shot proof"],
                        "tone": "direct-response",
                    },
                    "editing": {
                        "cut_style": "fixed_interval",
                        "clip_duration_seconds": 2,
                        "target_duration_seconds": 6,
                        "max_clip_count": 3,
                        "pacing": "fast",
                        "keep_original_order": True,
                    },
                    "delivery": {
                        "aspect_ratio": "9:16",
                        "width": 1080,
                        "height": 1920,
                        "fps": 30,
                        "format": "mp4",
                        "fit": "original",
                    },
                    "review_notes": "Check first three hooks.",
                },
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
                    "json_spec": {
                        "type": "concat",
                        "editing": {
                            "clip_duration_seconds": 3,
                            "max_clip_count": 1 if label == "short" else 2,
                        },
                        "delivery": {"format": "mp4", "fit": "original"},
                    },
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

    events_response = client.get(f"/api/tasks/{tasks[0]['id']}/events")
    assert events_response.status_code == 200
    assert events_response.json()[0]["message"] == "Task created"


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
                "tags": ["hook", "approved"],
            },
        )
        assert review_response.status_code == 200
        reviewed = review_response.json()
        assert reviewed["review_status"] == "approved"
        assert reviewed["review_notes"] == "Ready for ad testing."
        assert reviewed["review_feedback"]["reviewer_name"] == "Ada"
        assert reviewed["review_feedback"]["priority"] == "high"
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
                    "json_spec": {
                        "type": "concat",
                        "editing": {
                            "clip_duration_seconds": 3,
                            "max_clip_count": count,
                        },
                        "delivery": {"format": "mp4", "fit": "original"},
                    },
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
        safe_area_top=0,
        safe_area_bottom=0,
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
                "json_spec": {
                    "type": "concat",
                    "segments": {"segment_seconds": 3},
                    "selection": {"mode": "first_n", "count": 2},
                    "delivery": {"format": "mp4", "fit": "original"},
                    "transformations": {
                        "brightness": 0.03,
                        "contrast": 1.08,
                        "saturation": 1.12,
                        "playback_speed": 1.03,
                        "volume": 0.95,
                    },
                    "review_notes": "Confirm creative treatment and source rights.",
                },
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
                "json_spec": {
                    "type": "concat",
                    "segments": {"segment_seconds": 3},
                    "selection": {"mode": "first_n", "count": 1},
                    "output": {"width": 1080, "height": 1920, "fps": 30, "format": "mp4"},
                    "layout": {"fit": "cover"},
                },
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
