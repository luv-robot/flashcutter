from pathlib import Path
import json

import pytest


def test_import_approved_assets_writes_metadata(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from template_element_miner.asset_importer import import_approved_assets

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    image = np.full((90, 120, 3), 230, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (100, 70), (0, 180, 80), -1)
    crop_path = source_dir / "crop.png"
    debug_path = source_dir / "debug.jpg"
    frame_path = source_dir / "frame.jpg"
    cv2.imwrite(str(crop_path), image)
    cv2.imwrite(str(debug_path), image)
    cv2.imwrite(str(frame_path), image)
    approved_path = tmp_path / "approved_assets.jsonl"
    approved_path.write_text(
        json.dumps(
            {
                "approved": True,
                "asset_type": "cta_button",
                "subtype": "green",
                "source_file": "ad.mp4",
                "source_frame_id": "ad_f000001",
                "bbox": [10, 20, 120, 90],
                "width": 120,
                "height": 90,
                "detector": "bottom_cta_bar",
                "score": 0.82,
                "crop_path": str(crop_path),
                "debug_path": str(debug_path),
                "frame_path": str(frame_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    created = import_approved_assets(approved_path, tmp_path / "assets")

    assert len(created) == 1
    metadata = json.loads((created[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["asset_id"] == "asset_000001"
    assert metadata["asset_type"] == "cta_button"
    assert metadata["license_status"] == "needs_review"
    assert (created[0] / "asset.png").exists()
