from __future__ import annotations

from pathlib import Path
from typing import Optional
import re
import shutil

import cv2
import numpy as np

from template_element_miner.config import SUPPORTED_IMAGE_SUFFIXES, SUPPORTED_VIDEO_SUFFIXES


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-")
    return stem or "media"


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES


def is_video_path(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES


def collect_media_files(input_dir: Path) -> tuple[list[Path], list[Path]]:
    input_dir = Path(input_dir)
    candidates: list[Path] = []
    for child in input_dir.rglob("*"):
        if child.is_file():
            candidates.append(child)
    images = sorted({path for path in candidates if is_image_path(path)})
    videos = sorted({path for path in candidates if is_video_path(path)})
    return images, videos


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unable to read image: {path}")
    return image


def write_image(path: Path, image: np.ndarray, params: Optional[list[int]] = None) -> None:
    ensure_dir(path.parent)
    suffix = path.suffix.lower()
    encode_suffix = ".jpg" if suffix in {".jpeg", ".jpg"} else suffix
    ok, encoded = cv2.imencode(encode_suffix, image, params or [])
    if not ok:
        raise ValueError(f"Unable to encode image: {path}")
    encoded.tofile(str(path))


def copy_or_normalize_image(source: Path, destination: Path) -> tuple[int, int]:
    image = read_image(source)
    write_image(destination, image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    height, width = image.shape[:2]
    return width, height


def copy_file(source: Path, destination: Path) -> None:
    ensure_dir(destination.parent)
    shutil.copy2(source, destination)


def dominant_colors(path: Path, max_colors: int = 3) -> list[str]:
    image = read_image(path)
    image = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
    pixels = image.reshape((-1, 3)).astype(np.float32)
    cluster_count = max(1, min(max_colors, len(pixels)))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _compactness, labels, centers = cv2.kmeans(
        pixels,
        cluster_count,
        None,
        criteria,
        3,
        cv2.KMEANS_PP_CENTERS,
    )
    counts = np.bincount(labels.flatten(), minlength=cluster_count)
    ordered = sorted(range(cluster_count), key=lambda index: counts[index], reverse=True)
    colors: list[str] = []
    for index in ordered:
        blue, green, red = centers[index].astype(int).clip(0, 255)
        colors.append(f"#{red:02x}{green:02x}{blue:02x}")
    return colors
