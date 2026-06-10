from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from template_element_miner.config import DetectionConfig
from template_element_miner.schemas import CandidateRecord, FrameRecord, read_jsonl, write_jsonl
from template_element_miner.utils.image_io import ensure_dir, read_image, write_image
from template_element_miner.utils.visualization import save_bbox_debug


@dataclass
class BBoxCandidate:
    bbox: list[int]
    detector: str
    type_hint: str
    score: float


def detect_candidates(
    frames_dir: Path,
    output_dir: Path,
    config: Optional[DetectionConfig] = None,
) -> list[CandidateRecord]:
    config = config or DetectionConfig()
    frames_dir = Path(frames_dir)
    output_dir = Path(output_dir)
    frame_records = _load_frame_records(frames_dir)
    candidates_dir = ensure_dir(output_dir / "candidates")
    debug_dir = ensure_dir(output_dir / "debug")
    records: list[CandidateRecord] = []

    for frame_record in frame_records:
        frame_path = Path(frame_record.frame_path)
        image = read_image(frame_path)
        raw_boxes = (
            contour_rectangle_candidates(image)
            + high_contrast_banner_candidates(image)
            + border_frame_candidates(image)
            + bottom_cta_bar_candidates(image)
            + corner_badge_candidates(image)
        )
        filtered = filter_bbox_candidates(image, raw_boxes, config)
        for box in filtered:
            candidate_number = len(records) + 1
            candidate_id = f"cand_{candidate_number:06d}"
            x, y, width, height = box.bbox
            crop = image[y : y + height, x : x + width]
            crop_path = candidates_dir / f"{candidate_id}.png"
            debug_path = debug_dir / f"{candidate_id}.jpg"
            write_image(crop_path, crop)
            save_bbox_debug(frame_path, box.bbox, debug_path, f"{candidate_id} {box.detector}")
            frame_area = max(1, image.shape[0] * image.shape[1])
            records.append(
                CandidateRecord(
                    candidate_id=candidate_id,
                    source_frame_id=frame_record.frame_id,
                    source_file=frame_record.source_file,
                    frame_path=str(frame_path),
                    bbox=box.bbox,
                    width=width,
                    height=height,
                    area_ratio=round((width * height) / frame_area, 6),
                    aspect_ratio=round(width / max(1, height), 4),
                    detector=box.detector,
                    type_hint=box.type_hint,
                    score=round(float(box.score), 4),
                    crop_path=str(crop_path),
                    debug_path=str(debug_path),
                )
            )

    write_jsonl(output_dir / "candidates.jsonl", records)
    return records


def _load_frame_records(frames_dir: Path) -> list[FrameRecord]:
    metadata_path = frames_dir / "frames.jsonl"
    if not metadata_path.exists():
        metadata_path = frames_dir.parent / "frames.jsonl"
    rows = read_jsonl(metadata_path)
    return [FrameRecord(**row) for row in rows]


def contour_rectangle_candidates(image: np.ndarray) -> list[BBoxCandidate]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 60, 160)
    contours, _hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[BBoxCandidate] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width <= 0 or height <= 0:
            continue
        rect_area = width * height
        contour_area = max(1.0, cv2.contourArea(contour))
        rectangularity = min(1.0, contour_area / rect_area)
        if rectangularity < 0.2:
            continue
        aspect = width / max(1, height)
        type_hint = "banner_or_frame" if aspect > 1.8 else "layout_block"
        score = 0.42 + rectangularity * 0.42
        candidates.append(BBoxCandidate([x, y, width, height], "contour_rect", type_hint, score))
    return candidates


def high_contrast_banner_candidates(image: np.ndarray) -> list[BBoxCandidate]:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.convertScaleAbs(cv2.magnitude(grad_x, grad_y))
    _, threshold = cv2.threshold(magnitude, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, width // 30), 5))
    closed = cv2.morphologyEx(threshold, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _hierarchy = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[BBoxCandidate] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        aspect = box_width / max(1, box_height)
        if aspect < 2.0 or box_width < width * 0.22:
            continue
        if box_height > height * 0.45:
            continue
        crop = gray[y : y + box_height, x : x + box_width]
        score = min(0.96, 0.5 + float(crop.std()) / 120)
        candidates.append(BBoxCandidate([x, y, box_width, box_height], "high_contrast_banner", "title_bar", score))
    return candidates


def border_frame_candidates(image: np.ndarray) -> list[BBoxCandidate]:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 140)
    contours, _hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[BBoxCandidate] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area_ratio = (box_width * box_height) / max(1, width * height)
        aspect = box_width / max(1, box_height)
        if 0.04 <= area_ratio <= 0.58 and 0.35 <= aspect <= 3.2:
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.03 * perimeter, True)
            if len(approx) >= 4:
                score = min(0.94, 0.5 + area_ratio)
                candidates.append(BBoxCandidate([x, y, box_width, box_height], "border_frame", "product_frame", score))
    return candidates


def bottom_cta_bar_candidates(image: np.ndarray) -> list[BBoxCandidate]:
    height, width = image.shape[:2]
    bottom_start = int(height * 0.58)
    bottom = image[bottom_start:height, :]
    hsv = cv2.cvtColor(bottom, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    mask = cv2.inRange(saturation, 45, 255)
    bright_mask = cv2.inRange(value, 60, 255)
    mask = cv2.bitwise_and(mask, bright_mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(24, width // 12), 9))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _hierarchy = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[BBoxCandidate] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        absolute_y = y + bottom_start
        height_ratio = box_height / max(1, height)
        if box_width < width * 0.35:
            continue
        if not (0.04 <= height_ratio <= 0.28):
            continue
        score = 0.72 if absolute_y > height * 0.68 else 0.62
        candidates.append(BBoxCandidate([x, absolute_y, box_width, box_height], "bottom_cta_bar", "cta_button", score))
    return candidates


def corner_badge_candidates(image: np.ndarray) -> list[BBoxCandidate]:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _hierarchy = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[BBoxCandidate] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        center_x = x + box_width / 2
        center_y = y + box_height / 2
        near_corner = (center_x < width * 0.32 or center_x > width * 0.68) and (
            center_y < height * 0.32 or center_y > height * 0.68
        )
        area_ratio = (box_width * box_height) / max(1, width * height)
        aspect = box_width / max(1, box_height)
        if near_corner and 0.003 <= area_ratio <= 0.12 and 0.35 <= aspect <= 3.8:
            candidates.append(BBoxCandidate([x, y, box_width, box_height], "corner_badge", "discount_badge", 0.68))
    return candidates


def filter_bbox_candidates(
    image: np.ndarray,
    candidates: list[BBoxCandidate],
    config: Optional[DetectionConfig] = None,
) -> list[BBoxCandidate]:
    config = config or DetectionConfig()
    height, width = image.shape[:2]
    filtered: list[BBoxCandidate] = []
    for candidate in candidates:
        clipped = _clip_bbox(candidate.bbox, width, height)
        if clipped is None:
            continue
        x, y, box_width, box_height = clipped
        if box_width < config.min_width_px or box_height < config.min_height_px:
            continue
        area_ratio = (box_width * box_height) / max(1, width * height)
        if area_ratio < config.min_area_ratio or area_ratio > config.max_area_ratio:
            continue
        aspect = box_width / max(1, box_height)
        if aspect > config.max_thin_aspect or (1 / max(aspect, 0.001)) > config.max_thin_aspect:
            continue
        crop = image[y : y + box_height, x : x + box_width]
        if crop.size == 0:
            continue
        if float(crop.std()) < config.min_crop_stddev:
            continue
        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if float(cv2.Laplacian(gray_crop, cv2.CV_64F).var()) < config.min_blur_laplacian_var:
            continue
        filtered.append(
            BBoxCandidate(
                bbox=[x, y, box_width, box_height],
                detector=candidate.detector,
                type_hint=candidate.type_hint,
                score=float(candidate.score),
            )
        )
    return merge_overlapping_candidates(filtered, config.merge_iou_threshold)


def merge_overlapping_candidates(candidates: list[BBoxCandidate], iou_threshold: float) -> list[BBoxCandidate]:
    ordered = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    kept: list[BBoxCandidate] = []
    for candidate in ordered:
        if all(_iou(candidate.bbox, existing.bbox) < iou_threshold for existing in kept):
            kept.append(candidate)
    return sorted(kept, key=lambda candidate: (candidate.bbox[1], candidate.bbox[0], -candidate.score))


def _clip_bbox(bbox: list[int], frame_width: int, frame_height: int) -> Optional[list[int]]:
    x, y, width, height = [int(round(value)) for value in bbox]
    x = max(0, min(frame_width - 1, x))
    y = max(0, min(frame_height - 1, y))
    right = max(x + 1, min(frame_width, x + width))
    bottom = max(y + 1, min(frame_height, y + height))
    clipped_width = right - x
    clipped_height = bottom - y
    if clipped_width <= 0 or clipped_height <= 0:
        return None
    return [x, y, clipped_width, clipped_height]


def _iou(a: list[int], b: list[int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    inter_width = max(0, x2 - x1)
    inter_height = max(0, y2 - y1)
    intersection = inter_width * inter_height
    if intersection == 0:
        return 0.0
    union = aw * ah + bw * bh - intersection
    return intersection / max(1, union)
