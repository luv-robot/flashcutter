from app.services.ffmpeg import _video_filters


def test_video_filters_include_cover_regions_and_text_overlays() -> None:
    filters = _video_filters(
        width=1080,
        height=1920,
        fps=30,
        fit="cover",
        transformations={
            "contrast": 1.25,
            "cover_regions": [
                {
                    "x": 60,
                    "y": 1500,
                    "width": 960,
                    "height": 220,
                    "color": "black@0.78",
                }
            ],
            "text_overlays": [
                {
                    "text": "NEW OFFER",
                    "x": 88,
                    "y": 1550,
                    "font_size": 56,
                    "font_color": "white",
                    "box_color": "black@0.0",
                    "box_padding": 0,
                }
            ],
        },
    )

    assert "scale=1080:1920:force_original_aspect_ratio=increase" in filters
    assert "crop=1080:1920" in filters
    assert any(item.startswith("drawbox=x=60:y=1500") for item in filters)
    assert any("drawtext=text='NEW OFFER'" in item for item in filters)
