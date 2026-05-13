import pytest
from pydantic import ValidationError

from app.api.routes import normalize_template_spec
from app.schemas import TemplateSpec, TemplateSubtitleBarSpec


def _spec_with_bar(**bar_overrides) -> TemplateSpec:
    payload = {
        "type": "concat",
        "delivery": {
            "aspect_ratio": "9:16",
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
            "format": "mp4",
            "fit": "contain",
        },
        "subtitle_bar": {
            "enabled": True,
            "text": "真实记录",
            "position": "bottom",
            "font_size": 56,
            "bar_height": 160,
            **bar_overrides,
        },
    }
    return TemplateSpec.model_validate(payload)


def _as_dict(item):
    return item if isinstance(item, dict) else item.model_dump()


def test_bottom_bar_adds_cover_region_at_bottom() -> None:
    spec = _spec_with_bar()
    normalized = normalize_template_spec(spec)
    regions = [_as_dict(r) for r in normalized.transformations.cover_regions]
    assert len(regions) == 1
    region = regions[0]
    assert region["x"] == 0
    assert region["width"] == 1080
    assert region["height"] == 160
    assert region["y"] == 1760  # 1920 - 160


def test_top_bar_adds_cover_region_at_top() -> None:
    spec = _spec_with_bar(position="top")
    normalized = normalize_template_spec(spec)
    region = _as_dict(normalized.transformations.cover_regions[0])
    assert region["y"] == 0


def test_bar_adds_text_overlay_centered() -> None:
    spec = _spec_with_bar()
    normalized = normalize_template_spec(spec)
    overlays = [_as_dict(o) for o in normalized.transformations.text_overlays]
    assert len(overlays) == 1
    overlay = overlays[0]
    assert overlay["text"] == "真实记录"
    assert isinstance(overlay["x"], str)
    assert "text_w" in overlay["x"]


def test_bar_color_none_skips_drawbox() -> None:
    spec = _spec_with_bar(bar_color="none")
    normalized = normalize_template_spec(spec)
    assert normalized.transformations.cover_regions == []
    assert len(normalized.transformations.text_overlays) == 1


def test_bottom_bar_auto_sets_safe_area() -> None:
    spec = _spec_with_bar()
    normalized = normalize_template_spec(spec)
    assert normalized.layout.safe_area_bottom == 160
    assert normalized.layout.safe_area_top == 0


def test_top_bar_auto_sets_safe_area_top() -> None:
    spec = _spec_with_bar(position="top")
    normalized = normalize_template_spec(spec)
    assert normalized.layout.safe_area_top == 160
    assert normalized.layout.safe_area_bottom == 0


def test_operator_safe_area_preserved() -> None:
    payload = {
        "type": "concat",
        "delivery": {
            "aspect_ratio": "9:16",
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
            "format": "mp4",
            "fit": "contain",
            "safe_area_bottom": 300,
        },
        "subtitle_bar": {
            "enabled": True,
            "text": "x",
            "position": "bottom",
            "bar_height": 160,
        },
    }
    spec = TemplateSpec.model_validate(payload)
    normalized = normalize_template_spec(spec)
    assert normalized.layout.safe_area_bottom == 300


def test_bar_disabled_no_effect() -> None:
    payload = {
        "type": "concat",
        "delivery": {
            "aspect_ratio": "9:16",
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
            "format": "mp4",
            "fit": "contain",
        },
        "subtitle_bar": {"enabled": False, "text": ""},
    }
    spec = TemplateSpec.model_validate(payload)
    normalized = normalize_template_spec(spec)
    assert normalized.transformations.cover_regions == []
    assert normalized.transformations.text_overlays == []
    assert normalized.layout.safe_area_bottom == 0


def test_bar_position_validation() -> None:
    with pytest.raises(ValidationError):
        TemplateSubtitleBarSpec.model_validate(
            {"enabled": True, "text": "x", "position": "middle"}
        )
