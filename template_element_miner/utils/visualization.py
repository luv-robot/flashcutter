from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from template_element_miner.utils.image_io import ensure_dir, read_image, write_image


def draw_bbox(image: np.ndarray, bbox: list[int], label: Optional[str] = None) -> np.ndarray:
    x, y, width, height = bbox
    rendered = image.copy()
    color = (0, 230, 255)
    cv2.rectangle(rendered, (x, y), (x + width, y + height), color, 3)
    if label:
        cv2.putText(
            rendered,
            label,
            (x, max(20, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )
    return rendered


def save_bbox_debug(frame_path: Path, bbox: list[int], output_path: Path, label: str) -> None:
    image = read_image(frame_path)
    rendered = draw_bbox(image, bbox, label)
    write_image(output_path, rendered, [int(cv2.IMWRITE_JPEG_QUALITY), 90])


def make_contact_sheet(
    crop_paths: list[Path],
    output_path: Path,
    thumb_size: tuple[int, int] = (160, 120),
    columns: int = 5,
) -> None:
    ensure_dir(output_path.parent)
    if not crop_paths:
        canvas = np.full((thumb_size[1], thumb_size[0], 3), 245, dtype=np.uint8)
        write_image(output_path, canvas)
        return

    thumbs: list[np.ndarray] = []
    for path in crop_paths:
        image = read_image(path)
        height, width = image.shape[:2]
        scale = min(thumb_size[0] / width, thumb_size[1] / height)
        resized = cv2.resize(
            image,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        thumb = np.full((thumb_size[1], thumb_size[0], 3), 246, dtype=np.uint8)
        y = (thumb_size[1] - resized.shape[0]) // 2
        x = (thumb_size[0] - resized.shape[1]) // 2
        thumb[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
        thumbs.append(thumb)

    rows = (len(thumbs) + columns - 1) // columns
    canvas = np.full((rows * thumb_size[1], columns * thumb_size[0], 3), 238, dtype=np.uint8)
    for index, thumb in enumerate(thumbs):
        row, col = divmod(index, columns)
        y = row * thumb_size[1]
        x = col * thumb_size[0]
        canvas[y : y + thumb_size[1], x : x + thumb_size[0]] = thumb
    write_image(output_path, canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
