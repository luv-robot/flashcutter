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


def test_video_filters_include_timed_text_overlays() -> None:
    filters = _video_filters(
        width=1080,
        height=1920,
        fps=30,
        fit="cover",
        transformations={
            "text_overlays": [
                {
                    "text": "OPEN STRONG",
                    "x": 72,
                    "y": 118,
                    "font_size": 60,
                    "font_color": "white",
                    "box_color": "black@0.66",
                    "box_padding": 20,
                    "start_sec": 0,
                    "end_sec": 3.2,
                }
            ],
        },
    )

    assert any("enable='between(t,0,3.2)'" in item for item in filters)


def test_video_filters_expand_visual_style_groups() -> None:
    filters = _video_filters(
        width=1080,
        height=1920,
        fps=30,
        fit="cover",
        transformations={
            "visual_style": "punchy_social",
            "finishing_style": "film_grain",
        },
    )

    assert any(item.startswith("unsharp=") for item in filters)
    assert "eq=brightness=0.015:contrast=1.18:saturation=1.25" in filters
    assert "noise=alls=8:allf=t+u" in filters


def test_video_filters_include_horizontal_mirror() -> None:
    filters = _video_filters(
        width=1080,
        height=1920,
        fps=30,
        fit="cover",
        transformations={"orientation": "mirror_horizontal"},
    )

    assert "hflip" in filters


def test_video_filters_expand_motion_transition_and_texture_groups() -> None:
    filters = _video_filters(
        width=1080,
        height=1920,
        fps=30,
        fit="cover",
        transformations={
            "motion_style": "slow_pan",
            "transition_style": "flash_white",
            "texture_style": "subtle_grid",
        },
    )

    assert "scale=trunc(iw*1.08/2)*2:trunc(ih*1.08/2)*2" in filters
    assert any(item.startswith("crop=1080:1920") for item in filters)
    assert "fade=t=in:st=0:d=0.10:color=white" in filters
    assert "drawgrid=width=80:height=80:thickness=1:color=white@0.08" in filters
