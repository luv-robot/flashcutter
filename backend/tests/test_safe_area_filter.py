from app.services.ffmpeg import _video_filters


def test_safe_area_produces_offset_pad() -> None:
    filters = _video_filters(
        width=1080,
        height=1920,
        fps=30,
        fit="cover",
        safe_area_top=80,
        safe_area_bottom=200,
    )
    assert "scale=1080:1640:force_original_aspect_ratio=decrease" in filters
    assert "pad=1080:1920:(ow-iw)/2:80:black" in filters
    assert not any(item.startswith("crop=") for item in filters)


def test_zero_safe_area_falls_back_to_fit_mode() -> None:
    filters = _video_filters(
        width=1080,
        height=1920,
        fps=30,
        fit="cover",
        safe_area_top=0,
        safe_area_bottom=0,
    )
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in filters
    assert "crop=1080:1920" in filters


def test_safe_area_only_top() -> None:
    filters = _video_filters(
        width=1080,
        height=1920,
        fps=30,
        fit="contain",
        safe_area_top=160,
        safe_area_bottom=0,
    )
    assert "scale=1080:1760:force_original_aspect_ratio=decrease" in filters
    assert "pad=1080:1920:(ow-iw)/2:160:black" in filters
