import pytest


def test_filter_bbox_candidates_removes_tiny_and_merges_overlap() -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from template_element_miner.candidate_detector import BBoxCandidate, filter_bbox_candidates
    from template_element_miner.config import DetectionConfig

    image = np.full((240, 320, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (40, 70), (260, 135), (20, 80, 230), -1)
    cv2.putText(image, "SALE", (78, 112), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    boxes = [
        BBoxCandidate([40, 70, 220, 65], "contour_rect", "title_bar", 0.7),
        BBoxCandidate([42, 72, 216, 61], "high_contrast_banner", "title_bar", 0.9),
        BBoxCandidate([5, 5, 8, 8], "corner_badge", "discount_badge", 0.9),
    ]

    filtered = filter_bbox_candidates(
        image,
        boxes,
        DetectionConfig(min_crop_stddev=1.0, min_blur_laplacian_var=1.0),
    )

    assert len(filtered) == 1
    assert filtered[0].detector == "high_contrast_banner"
