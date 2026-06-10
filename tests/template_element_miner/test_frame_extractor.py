from pathlib import Path

import pytest


def test_extract_frames_normalizes_images(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from template_element_miner.frame_extractor import extract_frames
    from template_element_miner.schemas import read_jsonl

    input_dir = tmp_path / "input" / "images"
    input_dir.mkdir(parents=True)
    image = np.full((80, 120, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (15, 20), (90, 60), (0, 0, 255), -1)
    source_path = input_dir / "source.png"
    cv2.imwrite(str(source_path), image)

    output_dir = tmp_path / "output"
    records = extract_frames(tmp_path / "input", output_dir, fps=1)

    assert len(records) == 1
    assert records[0].source_type == "image"
    assert records[0].width == 120
    assert records[0].height == 80
    assert Path(records[0].frame_path).exists()
    assert len(read_jsonl(output_dir / "frames.jsonl")) == 1
