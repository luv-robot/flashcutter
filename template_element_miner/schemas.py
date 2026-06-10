from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional
import json


@dataclass
class FrameRecord:
    frame_id: str
    source_file: str
    source_type: str
    timestamp_sec: float
    frame_path: str
    width: int
    height: int


@dataclass
class CandidateRecord:
    candidate_id: str
    source_frame_id: str
    source_file: str
    frame_path: str
    bbox: list[int]
    width: int
    height: int
    area_ratio: float
    aspect_ratio: float
    detector: str
    type_hint: str
    score: float
    crop_path: str
    debug_path: str
    phash: Optional[str] = None
    cluster_id: Optional[str] = None
    dominant_colors: Optional[list[str]] = None


@dataclass
class ClusterRecord:
    cluster_id: str
    representative_candidate_id: str
    candidate_ids: list[str]
    type_hint: str
    contact_sheet_path: str


def dataclass_to_dict(record: Any) -> dict[str, Any]:
    data = asdict(record)
    return {key: value for key, value in data.items() if value is not None}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if hasattr(row, "__dataclass_fields__"):
                payload = dataclass_to_dict(row)
            else:
                payload = dict(row)
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
