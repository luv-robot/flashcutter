from __future__ import annotations

from pathlib import Path

import cv2

from template_element_miner.schemas import FrameRecord, write_jsonl
from template_element_miner.utils.image_io import (
    collect_media_files,
    copy_or_normalize_image,
    ensure_dir,
    safe_stem,
    write_image,
)


def extract_frames(input_dir: Path, output_dir: Path, fps: float = 1.0) -> list[FrameRecord]:
    if fps <= 0:
        raise ValueError("fps must be greater than 0")

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    frames_dir = ensure_dir(output_dir / "frames")
    images, videos = collect_media_files(input_dir)
    records: list[FrameRecord] = []

    for image_path in images:
        stem = safe_stem(image_path)
        frame_id = f"{stem}_img000001"
        destination = frames_dir / f"{frame_id}.jpg"
        width, height = copy_or_normalize_image(image_path, destination)
        records.append(
            FrameRecord(
                frame_id=frame_id,
                source_file=image_path.name,
                source_type="image",
                timestamp_sec=0.0,
                frame_path=str(destination),
                width=width,
                height=height,
            )
        )

    for video_path in videos:
        records.extend(_extract_video_frames(video_path, frames_dir, fps))

    records.sort(key=lambda record: record.frame_id)
    write_jsonl(output_dir / "frames.jsonl", records)
    write_jsonl(frames_dir / "frames.jsonl", records)
    return records


def _extract_video_frames(video_path: Path, frames_dir: Path, fps: float) -> list[FrameRecord]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Unable to open video: {video_path}")

    source_fps = capture.get(cv2.CAP_PROP_FPS) or fps
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, int(round(source_fps / fps)))
    stem = safe_stem(video_path)
    records: list[FrameRecord] = []
    frame_index = 0
    saved_index = 0

    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % step == 0:
            timestamp_sec = frame_index / source_fps if source_fps else float(saved_index)
            frame_id = f"{stem}_f{frame_index:06d}"
            destination = frames_dir / f"{frame_id}.jpg"
            write_image(destination, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            height, width = frame.shape[:2]
            records.append(
                FrameRecord(
                    frame_id=frame_id,
                    source_file=video_path.name,
                    source_type="video",
                    timestamp_sec=round(timestamp_sec, 3),
                    frame_path=str(destination),
                    width=width,
                    height=height,
                )
            )
            saved_index += 1
        frame_index += 1
        if frame_count and frame_index > frame_count:
            break

    capture.release()
    return records
