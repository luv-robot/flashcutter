import csv
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.ffmpeg import FFmpegError


def detect_text_regions(
    source_path: Path,
    output_dir: Path,
    width: Optional[int],
    height: Optional[int],
    duration_seconds: Optional[float],
) -> List[Dict[str, Any]]:
    if not width or not height:
        return []

    frame_path = output_dir / "text-detection-frame.png"
    timestamp = max(0.1, min(float(duration_seconds or 1.0) * 0.25, 2.0))
    _extract_frame(source_path=source_path, frame_path=frame_path, timestamp=timestamp)

    ocr_regions = _detect_with_tesseract(frame_path, width=width, height=height)
    if ocr_regions:
        return ocr_regions

    return heuristic_text_regions(width=width, height=height)


def heuristic_text_regions(width: int, height: int) -> List[Dict[str, Any]]:
    lower_height = max(80, int(height * 0.16))
    top_height = max(70, int(height * 0.12))
    side_margin = int(width * 0.06)
    return [
        {
            "x": side_margin,
            "y": max(0, height - lower_height - int(height * 0.05)),
            "width": width - side_margin * 2,
            "height": lower_height,
            "confidence": 0.35,
            "source": "heuristic_lower_third",
            "text": None,
        },
        {
            "x": side_margin,
            "y": int(height * 0.05),
            "width": width - side_margin * 2,
            "height": top_height,
            "confidence": 0.25,
            "source": "heuristic_top_title",
            "text": None,
        },
    ]


def _extract_frame(source_path: Path, frame_path: Path, timestamp: float) -> None:
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(source_path),
            "-frames:v",
            "1",
            str(frame_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise FFmpegError(message)


def _detect_with_tesseract(frame_path: Path, width: int, height: int) -> List[Dict[str, Any]]:
    if shutil.which("tesseract") is None:
        return []

    result = subprocess.run(
        ["tesseract", str(frame_path), "stdout", "--psm", "11", "tsv"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    regions = []
    reader = csv.DictReader(result.stdout.splitlines(), delimiter="\t")
    for row in reader:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        confidence = _float(row.get("conf"))
        if confidence is not None and confidence < 35:
            continue
        x = _int(row.get("left"))
        y = _int(row.get("top"))
        box_width = _int(row.get("width"))
        box_height = _int(row.get("height"))
        if x is None or y is None or box_width is None or box_height is None:
            continue
        if box_width < max(20, width * 0.02) or box_height < max(12, height * 0.015):
            continue
        regions.append(
            {
                "x": max(0, x - 12),
                "y": max(0, y - 10),
                "width": min(width - max(0, x - 12), box_width + 24),
                "height": min(height - max(0, y - 10), box_height + 20),
                "confidence": confidence / 100 if confidence is not None else 0.5,
                "source": "tesseract",
                "text": text,
            }
        )
    return _merge_nearby_regions(regions, width=width, height=height)


def _merge_nearby_regions(
    regions: List[Dict[str, Any]], width: int, height: int
) -> List[Dict[str, Any]]:
    if not regions:
        return []
    min_x = min(region["x"] for region in regions)
    min_y = min(region["y"] for region in regions)
    max_x = max(region["x"] + region["width"] for region in regions)
    max_y = max(region["y"] + region["height"] for region in regions)
    text = " ".join(str(region.get("text") or "") for region in regions).strip()
    confidence = sum(float(region.get("confidence") or 0) for region in regions) / len(regions)
    return [
        {
            "x": max(0, min_x),
            "y": max(0, min_y),
            "width": min(width, max_x) - max(0, min_x),
            "height": min(height, max_y) - max(0, min_y),
            "confidence": round(confidence, 3),
            "source": "tesseract_merged",
            "text": text or None,
        }
    ]


def _int(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _float(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None
