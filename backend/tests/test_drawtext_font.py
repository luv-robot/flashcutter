from app.services import ffmpeg as ffmpeg_module
from app.services.ffmpeg import _drawtext_filter, font_path


def test_drawtext_filter_includes_fontfile(monkeypatch, tmp_path) -> None:
    fake_font = tmp_path / "fake.ttf"
    fake_font.write_bytes(b"\x00")
    monkeypatch.setenv("FLASHCUTTER_FONT_PATH", str(fake_font))
    filter_str = _drawtext_filter(
        {
            "text": "你好",
            "x": 100,
            "y": 200,
            "font_size": 64,
            "font_color": "white",
            "box_color": None,
            "box_padding": 0,
        }
    )
    assert f"fontfile={str(fake_font)}" in filter_str
    assert "text='你好'" in filter_str


def test_font_path_prefers_env_override(monkeypatch, tmp_path) -> None:
    custom = tmp_path / "custom.otf"
    custom.write_bytes(b"\x00")
    monkeypatch.setenv("FLASHCUTTER_FONT_PATH", str(custom))
    assert font_path() == str(custom)


def test_font_path_ignores_missing_env(monkeypatch, tmp_path) -> None:
    missing = tmp_path / "does_not_exist.ttf"
    monkeypatch.setenv("FLASHCUTTER_FONT_PATH", str(missing))
    # Should fall through to system fallbacks (or return None if none present).
    result = font_path()
    assert result != str(missing)


def test_drawtext_with_expression_position(monkeypatch, tmp_path) -> None:
    fake_font = tmp_path / "fake.ttf"
    fake_font.write_bytes(b"\x00")
    monkeypatch.setenv("FLASHCUTTER_FONT_PATH", str(fake_font))
    filter_str = _drawtext_filter(
        {
            "text": "立即购买",
            "x": "(w-text_w)/2",
            "y": 1700,
            "font_size": 56,
            "font_color": "white",
            "box_color": None,
        }
    )
    # ffmpeg expression colons must be escaped in the filter string.
    assert "x=(w-text_w)/2" in filter_str
    assert "y=1700" in filter_str
