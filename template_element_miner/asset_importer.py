from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from template_element_miner.schemas import read_jsonl, write_json
from template_element_miner.utils.image_io import copy_file, dominant_colors, ensure_dir


def import_approved_assets(approved_path: Path, assets_dir: Path) -> list[Path]:
    approved_path = Path(approved_path)
    assets_dir = ensure_dir(Path(assets_dir))
    approved_rows = [row for row in read_jsonl(approved_path) if row.get("approved", True)]
    created: list[Path] = []

    next_index = _next_asset_index(assets_dir)
    for row in approved_rows:
        asset_id = f"asset_{next_index:06d}"
        next_index += 1
        asset_dir = ensure_dir(assets_dir / asset_id)
        crop_path = Path(row["crop_path"])
        debug_path = Path(row.get("debug_path") or row["crop_path"])
        frame_path = Path(row.get("frame_path") or row["crop_path"])
        asset_path = asset_dir / "asset.png"
        preview_path = asset_dir / "preview.jpg"
        source_frame_path = asset_dir / "source_frame.jpg"
        copy_file(crop_path, asset_path)
        copy_file(debug_path, preview_path)
        copy_file(frame_path, source_frame_path)
        colors = row.get("dominant_colors") or dominant_colors(asset_path)
        metadata = {
            "asset_id": asset_id,
            "asset_type": row.get("asset_type", "unknown"),
            "subtype": row.get("subtype", "unknown"),
            "source_file": row.get("source_file"),
            "source_frame_id": row.get("source_frame_id"),
            "bbox": row.get("bbox"),
            "width": row.get("width"),
            "height": row.get("height"),
            "dominant_colors": colors,
            "detector": row.get("detector"),
            "reusability_score": row.get("score"),
            "approved": True,
            "license_status": row.get("license_status", "needs_review"),
            "created_at": date.today().isoformat(),
        }
        write_json(asset_dir / "metadata.json", metadata)
        created.append(asset_dir)
    return created


def _next_asset_index(assets_dir: Path) -> int:
    highest = 0
    for path in assets_dir.glob("asset_*"):
        if not path.is_dir():
            continue
        try:
            highest = max(highest, int(path.name.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return highest + 1
