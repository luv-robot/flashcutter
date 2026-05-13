import argparse
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


def raise_with_body(response) -> None:
    try:
        response.raise_for_status()
    except Exception as exc:
        raise SystemExit(f"{exc}\nResponse body: {response.text}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the backend MVP smoke path.")
    parser.add_argument("video_path", type=Path)
    parser.add_argument("--segment-seconds", type=float, default=3.0)
    args = parser.parse_args()

    if not args.video_path.exists():
        raise SystemExit(f"Video file not found: {args.video_path}")

    with TestClient(app) as client:
        template_response = client.get("/api/templates")
        raise_with_body(template_response)
        templates = template_response.json()
        if not templates:
            raise SystemExit("No templates found.")
        template_id = templates[0]["id"]

        with args.video_path.open("rb") as video_file:
            upload_response = client.post(
                "/api/assets/upload",
                files={"file": (args.video_path.name, video_file, "video/mp4")},
            )
        raise_with_body(upload_response)
        asset = upload_response.json()

        segment_response = client.post(
            f"/api/assets/{asset['id']}/segment",
            params={"segment_seconds": args.segment_seconds},
        )
        raise_with_body(segment_response)
        segments = segment_response.json()

        task_response = client.post(
            "/api/tasks",
            json={
                "name": "smoke-test",
                "asset_id": asset["id"],
                "template_id": template_id,
                "params_json": {},
            },
        )
        raise_with_body(task_response)
        task = task_response.json()

        plan_response = client.post(f"/api/tasks/{task['id']}/render-plan")
        raise_with_body(plan_response)
        render_plan = plan_response.json()

        render_response = client.post(f"/api/tasks/{task['id']}/render")
        raise_with_body(render_response)
        output = render_response.json()

    output_path = Path(output["file_path"])
    if not output_path.exists():
        raise SystemExit(f"Output file missing: {output_path}")

    print("Backend smoke path completed.")
    print(f"asset_id={asset['id']}")
    print(f"segments={len(segments)}")
    print(f"task_id={task['id']}")
    print(f"render_plan_id={render_plan['id']}")
    print(f"output_id={output['id']}")
    print(f"output_path={output_path}")


if __name__ == "__main__":
    main()
