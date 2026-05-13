import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class FFmpegError(RuntimeError):
    pass


_FONT_FALLBACKS = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def font_path() -> Optional[str]:
    """Resolve a CJK-capable font file for drawtext.

    Order: FLASHCUTTER_FONT_PATH env var, then known macOS/Linux locations.
    Returns None only if nothing is found — callers should treat that as a
    fatal config issue when CJK rendering is required.
    """
    env_value = os.getenv("FLASHCUTTER_FONT_PATH")
    if env_value and Path(env_value).exists():
        return env_value
    for candidate in _FONT_FALLBACKS:
        if Path(candidate).exists():
            return candidate
    return None


def _run(command: List[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise FFmpegError(message)
    return result


def probe_media(path: Path) -> Dict[str, Any]:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    payload = json.loads(result.stdout)
    video_stream = next(
        (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
        {},
    )
    duration = payload.get("format", {}).get("duration") or video_stream.get("duration")
    return {
        "duration_seconds": float(duration) if duration else None,
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": _parse_fps(video_stream.get("avg_frame_rate")),
    }


def split_fixed_segments(
    source_path: Path,
    output_dir: Path,
    duration_seconds: float,
    segment_seconds: float,
) -> List[Dict[str, Any]]:
    if duration_seconds <= 0:
        raise FFmpegError("Source duration must be positive before splitting.")

    segment_count = max(1, math.ceil(duration_seconds / segment_seconds))
    segments = []
    for index in range(segment_count):
        start_time = index * segment_seconds
        remaining = max(0.0, duration_seconds - start_time)
        clip_duration = min(segment_seconds, remaining)
        if clip_duration <= 0:
            continue

        output_path = output_dir / f"{index + 1:04d}.mp4"
        _run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start_time:.3f}",
                "-i",
                str(source_path),
                "-t",
                f"{clip_duration:.3f}",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-pix_fmt",
                "yuv420p",
                "-avoid_negative_ts",
                "make_zero",
                str(output_path),
            ]
        )
        segments.append(
            {
                "index": index,
                "start_time": start_time,
                "end_time": start_time + clip_duration,
                "duration_seconds": clip_duration,
                "file_path": str(output_path),
            }
        )
    return segments


def render_concat(segment_paths: Iterable[Path], concat_file: Path, output_path: Path) -> None:
    lines = []
    for path in segment_paths:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    concat_file.write_text("\n".join(lines) + "\n")

    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output_path),
        ]
    )


def render_timeline(
    segment_paths: Iterable[Path],
    concat_file: Path,
    output_path: Path,
    width: Optional[int] = None,
    height: Optional[int] = None,
    fps: Optional[float] = None,
    fit: str = "original",
    transformations: Optional[Dict[str, Any]] = None,
    safe_area_top: int = 0,
    safe_area_bottom: int = 0,
) -> None:
    normalized_dir = concat_file.parent / concat_file.stem
    normalized_dir.mkdir(parents=True, exist_ok=True)

    normalized_paths = []
    for index, segment_path in enumerate(segment_paths, start=1):
        normalized_path = normalized_dir / f"{index:04d}.mp4"
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(segment_path),
        ]
        video_filters = _video_filters(
            width=width,
            height=height,
            fps=fps,
            fit=fit,
            transformations=transformations,
            safe_area_top=safe_area_top,
            safe_area_bottom=safe_area_bottom,
        )
        audio_filters = _audio_filters(transformations=transformations)
        if video_filters:
            command.extend(["-vf", ",".join(video_filters)])
        if transformations and transformations.get("mute_audio"):
            command.append("-an")
        elif audio_filters:
            command.extend(["-af", ",".join(audio_filters)])
        command.extend(
            [
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(normalized_path),
            ]
        )
        _run(command)
        normalized_paths.append(normalized_path)

    render_concat(normalized_paths, concat_file, output_path)


def render_card_clip(
    *,
    output_path: Path,
    duration_seconds: float,
    width: int,
    height: int,
    fps: float,
    text: str,
    subtitle: Optional[str] = None,
    background_color: str = "black",
    font_color: str = "white",
    font_size: int = 72,
    subtitle_font_color: str = "white",
    subtitle_font_size: int = 40,
) -> None:
    """Render a single solid-background MP4 with one or two lines of centered text.

    The output codec / dims / fps must match the surrounding seed video so the
    card can be concatenated without a second transcode pass.
    """
    if not text or not text.strip():
        raise FFmpegError("card text cannot be empty")
    if duration_seconds <= 0:
        raise FFmpegError("card duration must be positive")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    font = font_path()
    filters = [_card_drawtext(text, font_size, font_color, font, subtitle is not None, position="primary")]
    if subtitle and subtitle.strip():
        filters.append(
            _card_drawtext(
                subtitle, subtitle_font_size, subtitle_font_color, font,
                has_subtitle=True, position="subtitle",
            )
        )

    bg = _filter_value(background_color)
    duration = f"{duration_seconds:.3f}"
    command = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={bg}:s={width}x{height}:r={fps}:d={duration}",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-shortest",
        "-t", duration,
        "-vf", ",".join(filters),
        "-r", str(fps),
        "-fps_mode", "cfr",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    _run(command)


def _card_drawtext(
    text: str,
    font_size: int,
    font_color: str,
    font: Optional[str],
    has_subtitle: bool,
    position: str,
) -> str:
    if position == "primary":
        y_expr = "(h-text_h)/2-line_h/2" if has_subtitle else "(h-text_h)/2"
    else:
        y_expr = "(h-text_h)/2+line_h"
    parts = [
        f"drawtext=text='{_drawtext_escape(text)}'",
        "x=(w-text_w)/2",
        f"y={y_expr}",
        f"fontsize={font_size}",
        f"fontcolor={_filter_value(font_color)}",
    ]
    if font:
        parts.append(f"fontfile={_filter_value(font)}")
    return ":".join(parts)


def _video_filters(
    width: Optional[int],
    height: Optional[int],
    fps: Optional[float],
    fit: str,
    transformations: Optional[Dict[str, Any]] = None,
    safe_area_top: int = 0,
    safe_area_bottom: int = 0,
) -> List[str]:
    filters = []
    if width and height:
        if safe_area_top or safe_area_bottom:
            content_height = height - safe_area_top - safe_area_bottom
            if content_height <= 0:
                raise FFmpegError(
                    "safe_area_top + safe_area_bottom must leave room for content"
                )
            filters.extend(
                [
                    f"scale={width}:{content_height}:force_original_aspect_ratio=decrease",
                    f"pad={width}:{height}:(ow-iw)/2:{safe_area_top}:black",
                ]
            )
        elif fit == "cover":
            filters.extend(
                [
                    f"scale={width}:{height}:force_original_aspect_ratio=increase",
                    f"crop={width}:{height}",
                ]
            )
        elif fit in ("contain", "original"):
            filters.extend(
                [
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
                ]
            )
        else:
            raise FFmpegError(f"Unsupported fit mode: {fit}")
    if fps:
        filters.append(f"fps={fps}")
    if transformations:
        eq_parts = []
        brightness = transformations.get("brightness")
        contrast = transformations.get("contrast")
        saturation = transformations.get("saturation")
        if brightness is not None:
            eq_parts.append(f"brightness={_bounded_float(brightness, -1.0, 1.0)}")
        if contrast is not None:
            eq_parts.append(f"contrast={_bounded_float(contrast, 0.0, 3.0)}")
        if saturation is not None:
            eq_parts.append(f"saturation={_bounded_float(saturation, 0.0, 3.0)}")
        if eq_parts:
            filters.append(f"eq={':'.join(eq_parts)}")

        playback_speed = transformations.get("playback_speed")
        if playback_speed is not None:
            speed = _bounded_float(playback_speed, 0.5, 2.0)
            filters.append(f"setpts={1 / speed:.6f}*PTS")

        for region in transformations.get("cover_regions") or []:
            filters.append(_drawbox_filter(region))

        for overlay in transformations.get("text_overlays") or []:
            filters.append(_drawtext_filter(overlay))
    return filters


def _drawbox_filter(region: Dict[str, Any]) -> str:
    return (
        "drawbox="
        f"x={_non_negative_int(region.get('x'), 'cover_regions.x')}:"
        f"y={_non_negative_int(region.get('y'), 'cover_regions.y')}:"
        f"w={_positive_int(region.get('width'), 'cover_regions.width')}:"
        f"h={_positive_int(region.get('height'), 'cover_regions.height')}:"
        f"color={_filter_value(region.get('color') or 'black@0.82')}:"
        "t=fill"
    )


def _drawtext_filter(overlay: Dict[str, Any]) -> str:
    text = str(overlay.get("text") or "").strip()
    if not text:
        raise FFmpegError("text_overlays.text cannot be empty")
    box_color = overlay.get("box_color")
    parts = [
        "drawtext="
        f"text='{_drawtext_escape(text)}'",
        f"x={_drawtext_position(overlay.get('x'), 'text_overlays.x')}",
        f"y={_drawtext_position(overlay.get('y'), 'text_overlays.y')}",
        f"fontsize={_positive_int(overlay.get('font_size') or 54, 'text_overlays.font_size')}",
        f"fontcolor={_filter_value(overlay.get('font_color') or 'white')}",
    ]
    font = font_path()
    if font:
        parts.append(f"fontfile={_filter_value(font)}")
    if box_color:
        parts.extend(
            [
                "box=1",
                f"boxcolor={_filter_value(box_color)}",
                f"boxborderw={_non_negative_int(overlay.get('box_padding') or 0, 'text_overlays.box_padding')}",
            ]
        )
    return ":".join(parts)


def _drawtext_position(value: Any, field_name: str) -> str:
    """Accept either an integer pixel coordinate or an ffmpeg expression."""
    if isinstance(value, str) and value:
        return _filter_value(value)
    return str(_non_negative_int(value, field_name))


def _audio_filters(transformations: Optional[Dict[str, Any]] = None) -> List[str]:
    if not transformations:
        return []

    filters = []
    volume = transformations.get("volume")
    if volume is not None:
        filters.append(f"volume={_bounded_float(volume, 0.0, 3.0)}")

    playback_speed = transformations.get("playback_speed")
    if playback_speed is not None:
        filters.append(f"atempo={_bounded_float(playback_speed, 0.5, 2.0)}")
    return filters


def _bounded_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FFmpegError(f"Expected numeric transformation value, got {value!r}") from exc
    if number < minimum or number > maximum:
        raise FFmpegError(
            f"Transformation value {number} must be between {minimum} and {maximum}"
        )
    return number


def _non_negative_int(value: Any, field_name: str) -> int:
    number = _positive_or_zero_int(value, field_name)
    if number < 0:
        raise FFmpegError(f"{field_name} must be non-negative")
    return number


def _positive_int(value: Any, field_name: str) -> int:
    number = _positive_or_zero_int(value, field_name)
    if number <= 0:
        raise FFmpegError(f"{field_name} must be positive")
    return number


def _positive_or_zero_int(value: Any, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise FFmpegError(f"Expected integer {field_name}, got {value!r}") from exc


def _filter_value(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace(":", "\\:")


def _drawtext_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("%", "\\%")
    )


def _parse_fps(value: Optional[str]) -> Optional[float]:
    if not value or value == "0/0":
        return None
    if "/" not in value:
        return float(value)
    numerator, denominator = value.split("/", 1)
    denominator_float = float(denominator)
    if denominator_float == 0:
        return None
    return float(numerator) / denominator_float
