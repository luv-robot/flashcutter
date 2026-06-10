from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from template_element_miner.utils.hashing import hamming_distance, phash_path


def ensure_candidate_phashes(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for candidate in candidates:
        row = dict(candidate)
        if not row.get("phash"):
            row["phash"] = phash_path(Path(row["crop_path"]))
        updated.append(row)
    return updated


def deduplicate_candidates(
    candidates: list[dict[str, Any]],
    max_distance: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    candidates = ensure_candidate_phashes(candidates)
    ordered = sorted(candidates, key=lambda row: float(row.get("score", 0)), reverse=True)
    representatives: list[dict[str, Any]] = []
    duplicate_map: dict[str, list[str]] = {}
    for candidate in ordered:
        matched_id: Optional[str] = None
        for representative in representatives:
            if hamming_distance(candidate.get("phash"), representative.get("phash")) <= max_distance:
                matched_id = str(representative["candidate_id"])
                break
        if matched_id:
            duplicate_map.setdefault(matched_id, []).append(str(candidate["candidate_id"]))
        else:
            representatives.append(candidate)
            duplicate_map.setdefault(str(candidate["candidate_id"]), [])
    return representatives, duplicate_map
