import pytest

from app.api.routes import validate_output_metadata
from app.services.ffmpeg import FFmpegError


def test_output_metadata_allows_minor_fps_probe_drift() -> None:
    validate_output_metadata(
        metadata={"width": 1080, "height": 1920, "fps": 29.46},
        output_spec={"width": 1080, "height": 1920, "fps": 30.0},
    )


def test_output_metadata_rejects_large_fps_mismatch() -> None:
    with pytest.raises(FFmpegError):
        validate_output_metadata(
            metadata={"width": 1080, "height": 1920, "fps": 24.0},
            output_spec={"width": 1080, "height": 1920, "fps": 30.0},
        )
