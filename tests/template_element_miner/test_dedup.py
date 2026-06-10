from pathlib import Path

import pytest


def test_phash_dedup_groups_identical_crops(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from template_element_miner.dedup import deduplicate_candidates
    from template_element_miner.utils.hashing import hamming_distance, phash_path

    image = np.full((80, 160, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (140, 60), (0, 100, 240), -1)
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    cv2.imwrite(str(first), image)
    cv2.imwrite(str(second), image)

    assert hamming_distance(phash_path(first), phash_path(second)) == 0

    representatives, duplicates = deduplicate_candidates(
        [
            {"candidate_id": "cand_000001", "crop_path": str(first), "score": 0.7},
            {"candidate_id": "cand_000002", "crop_path": str(second), "score": 0.9},
        ],
        max_distance=0,
    )

    assert [row["candidate_id"] for row in representatives] == ["cand_000002"]
    assert duplicates["cand_000002"] == ["cand_000001"]
