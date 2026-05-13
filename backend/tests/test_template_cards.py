import pytest
from pydantic import ValidationError

from app.api.routes import normalize_template_spec, validate_render_spec
from app.schemas import (
    TemplateCardSpec,
    TemplateDeliverySpec,
    TemplateSpec,
    TemplateSubtitleBarSpec,
)
from fastapi import HTTPException


def _base_spec(**overrides) -> TemplateSpec:
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
    }
    payload.update(overrides)
    return TemplateSpec.model_validate(payload)


def test_intro_card_enabled_requires_text() -> None:
    with pytest.raises(ValidationError):
        TemplateCardSpec.model_validate({"enabled": True, "text": ""})


def test_intro_card_disabled_allows_empty_text() -> None:
    card = TemplateCardSpec.model_validate({"enabled": False, "text": ""})
    assert card.enabled is False
    assert card.text == ""


def test_card_duration_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        TemplateCardSpec.model_validate(
            {"enabled": True, "text": "x", "duration_seconds": 10.0}
        )


def test_normalize_preserves_cards() -> None:
    spec = _base_spec(
        intro_card={
            "enabled": True,
            "text": "3 秒看懂",
            "duration_seconds": 1.2,
        },
        outro_card={
            "enabled": True,
            "text": "立即购买",
            "duration_seconds": 1.5,
        },
    )
    normalized = normalize_template_spec(spec)
    assert normalized.intro_card and normalized.intro_card.enabled
    assert normalized.intro_card.text == "3 秒看懂"
    assert normalized.outro_card and normalized.outro_card.enabled
    assert normalized.outro_card.text == "立即购买"


def test_validate_render_spec_requires_dims_for_cards() -> None:
    spec = TemplateSpec.model_validate(
        {
            "type": "concat",
            "intro_card": {"enabled": True, "text": "Hi"},
        }
    )
    spec = normalize_template_spec(spec)
    with pytest.raises(HTTPException) as exc:
        validate_render_spec(spec)
    assert "delivery.width, height, and fps" in exc.value.detail


def test_validate_render_spec_accepts_cards_with_dims() -> None:
    spec = _base_spec(
        intro_card={"enabled": True, "text": "Hi", "duration_seconds": 1.0},
    )
    spec = normalize_template_spec(spec)
    validate_render_spec(spec)  # should not raise


def test_safe_area_dimensions_rejected_when_no_room() -> None:
    with pytest.raises(ValidationError):
        TemplateDeliverySpec.model_validate(
            {
                "width": 1080,
                "height": 1920,
                "safe_area_top": 1000,
                "safe_area_bottom": 1000,
            }
        )
