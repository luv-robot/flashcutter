from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from template_element_miner.config import ClusterConfig
from template_element_miner.dedup import deduplicate_candidates, ensure_candidate_phashes
from template_element_miner.schemas import ClusterRecord, dataclass_to_dict, read_jsonl, write_json, write_jsonl
from template_element_miner.utils.hashing import hamming_distance
from template_element_miner.utils.image_io import dominant_colors, ensure_dir
from template_element_miner.utils.visualization import make_contact_sheet


def cluster_candidates(
    candidates_path: Path,
    output_dir: Path,
    config: Optional[ClusterConfig] = None,
) -> list[ClusterRecord]:
    config = config or ClusterConfig()
    output_dir = ensure_dir(Path(output_dir))
    candidates_path = Path(candidates_path)
    candidates = ensure_candidate_phashes(read_jsonl(candidates_path))
    for candidate in candidates:
        if not candidate.get("dominant_colors"):
            candidate["dominant_colors"] = dominant_colors(Path(candidate["crop_path"]))

    representatives, duplicate_map = deduplicate_candidates(candidates, config.duplicate_phash_distance)
    assigned: set[str] = set()
    clusters: list[ClusterRecord] = []

    for representative in representatives:
        representative_id = str(representative["candidate_id"])
        if representative_id in assigned:
            continue
        member_ids = [representative_id]
        assigned.add(representative_id)
        for duplicate_id in duplicate_map.get(representative_id, []):
            if duplicate_id not in assigned:
                member_ids.append(duplicate_id)
                assigned.add(duplicate_id)

        for candidate in representatives:
            candidate_id = str(candidate["candidate_id"])
            if candidate_id in assigned:
                continue
            if _same_cluster(representative, candidate, config):
                member_ids.append(candidate_id)
                assigned.add(candidate_id)
                for duplicate_id in duplicate_map.get(candidate_id, []):
                    if duplicate_id not in assigned:
                        member_ids.append(duplicate_id)
                        assigned.add(duplicate_id)

        cluster_id = f"cluster_{len(clusters) + 1:04d}"
        contact_sheet_path = output_dir / f"{cluster_id}.jpg"
        member_rows = [candidate for candidate in candidates if str(candidate["candidate_id"]) in set(member_ids)]
        crop_paths = [Path(row["crop_path"]) for row in member_rows[:25]]
        make_contact_sheet(
            crop_paths,
            contact_sheet_path,
            thumb_size=config.contact_sheet_thumb_size,
            columns=config.contact_sheet_columns,
        )
        for row in member_rows:
            row["cluster_id"] = cluster_id
        clusters.append(
            ClusterRecord(
                cluster_id=cluster_id,
                representative_candidate_id=representative_id,
                candidate_ids=member_ids,
                type_hint=str(representative.get("type_hint", "unknown")),
                contact_sheet_path=str(contact_sheet_path),
            )
        )

    write_json(output_dir.parent / "clusters.json", [dataclass_to_dict(cluster) for cluster in clusters])
    write_jsonl(candidates_path, candidates)
    write_jsonl(output_dir.parent / "candidates_clustered.jsonl", candidates)
    return clusters


def _same_cluster(a: dict[str, Any], b: dict[str, Any], config: ClusterConfig) -> bool:
    if hamming_distance(a.get("phash"), b.get("phash")) > config.cluster_phash_distance:
        return False
    aspect_a = float(a.get("aspect_ratio", 0))
    aspect_b = float(b.get("aspect_ratio", 0))
    if abs(aspect_a - aspect_b) > config.aspect_ratio_tolerance * max(1.0, aspect_a, aspect_b):
        return False
    area_a = float(a.get("area_ratio", 0))
    area_b = float(b.get("area_ratio", 0))
    if abs(area_a - area_b) > config.area_ratio_tolerance:
        return False
    if a.get("detector") != b.get("detector") and a.get("type_hint") != b.get("type_hint"):
        return False
    return _dominant_color_distance(a, b) <= config.dominant_color_distance


def _dominant_color_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    colors_a = a.get("dominant_colors") or ["#000000"]
    colors_b = b.get("dominant_colors") or ["#000000"]
    return min(_hex_distance(color_a, color_b) for color_a in colors_a for color_b in colors_b)


def _hex_distance(color_a: str, color_b: str) -> float:
    def parse(color: str) -> tuple[int, int, int]:
        cleaned = color.lstrip("#")
        return int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)

    ar, ag, ab = parse(color_a)
    br, bg, bb = parse(color_b)
    return ((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2) ** 0.5
