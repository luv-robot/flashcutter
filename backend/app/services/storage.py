from pathlib import Path
from urllib.parse import urlparse

from fastapi import UploadFile

from app.config import get_settings


def storage_root() -> Path:
    return get_settings().storage_root


def ensure_storage_dirs() -> None:
    for directory in (
        "uploads",
        "segments",
        "outputs",
        "temp",
        "analysis",
        "music",
        "ai_assets",
        "ai_clone",
    ):
        (storage_root() / directory).mkdir(parents=True, exist_ok=True)


def asset_upload_path(asset_id: int, original_filename: str) -> Path:
    suffix = Path(original_filename).suffix or ".mp4"
    return storage_root() / "uploads" / f"asset-{asset_id}{suffix}"


def music_upload_path(track_id: int, original_filename: str) -> Path:
    suffix = Path(original_filename).suffix or ".mp3"
    return storage_root() / "music" / f"music-{track_id}{suffix}"


def ai_asset_upload_path(asset_id: int, original_filename: str) -> Path:
    suffix = Path(original_filename).suffix or ".mp4"
    return storage_root() / "ai_assets" / f"ai-asset-{asset_id}{suffix}"


def ai_asset_source_image_path(asset_id: int, original_filename: str) -> Path:
    suffix = Path(original_filename).suffix or ".png"
    return storage_root() / "ai_assets" / f"ai-asset-{asset_id}-source{suffix}"


def ai_asset_generated_video_path(asset_id: int) -> Path:
    return storage_root() / "ai_assets" / f"ai-asset-{asset_id}-generated.mp4"


def ai_clone_reference_path(job_id: int, original_filename: str) -> Path:
    suffix = Path(original_filename).suffix or ".bin"
    path = storage_root() / "ai_clone" / f"clone-job-{job_id}-reference{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ai_clone_output_path(job_id: int) -> Path:
    path = storage_root() / "ai_clone" / f"clone-job-{job_id}-output.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ai_clone_conditioning_image_path(job_id: int) -> Path:
    path = storage_root() / "ai_clone" / f"clone-job-{job_id}-conditioning.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def filename_from_url(url: str) -> str:
    path = urlparse(url).path
    filename = Path(path).name
    return filename or "remote-video.mp4"


def asset_segments_dir(asset_id: int) -> Path:
    path = storage_root() / "segments" / f"asset-{asset_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def task_output_path(task_id: int) -> Path:
    path = storage_root() / "outputs" / f"task-{task_id}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def concat_list_path(task_id: int) -> Path:
    path = storage_root() / "temp" / f"task-{task_id}-concat.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def asset_analysis_dir(asset_id: int) -> Path:
    path = storage_root() / "analysis" / f"asset-{asset_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload_file(upload_file: UploadFile, destination: Path) -> int:
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        while chunk := await upload_file.read(1024 * 1024):
            size += len(chunk)
            output.write(chunk)
    return size
