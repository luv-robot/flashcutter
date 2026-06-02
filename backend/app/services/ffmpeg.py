import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class FFmpegError(RuntimeError):
    pass


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


def extract_video_frame(source_path: Path, output_path: Path, timestamp_seconds: float = 0.0) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp_seconds:.3f}",
            "-i",
            str(source_path),
            "-frames:v",
            "1",
            str(output_path),
        ]
    )


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


def replace_audio_track(
    video_path: Path,
    music_path: Path,
    output_path: Path,
    duration_seconds: Optional[float],
    volume: float = 1.0,
    loop: bool = True,
) -> None:
    if duration_seconds is None or duration_seconds <= 0:
        raise FFmpegError("Video duration is required before replacing audio.")

    command = ["ffmpeg", "-y", "-i", str(video_path)]
    if loop:
        command.extend(["-stream_loop", "-1"])
    command.extend(
        [
            "-i",
            str(music_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-af",
            f"volume={_bounded_float(volume, 0.0, 3.0)}",
            "-t",
            f"{duration_seconds:.3f}",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    _run(command)


def render_image_motion_clip(
    image_path: Path,
    output_path: Path,
    duration_seconds: float,
    width: int = 1080,
    height: int = 1920,
    fps: float = 30.0,
) -> None:
    if duration_seconds <= 0:
        raise FFmpegError("AI clip duration must be positive.")
    frame_count = max(1, int(duration_seconds * fps))
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        (
            "zoompan="
            "z='min(zoom+0.0012,1.08)':"
            f"d={frame_count}:"
            f"s={width}x{height}:"
            f"fps={fps}"
        ),
        "format=yuv420p",
    ]
    _run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-t",
            f"{duration_seconds:.3f}",
            "-vf",
            ",".join(filters),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(output_path),
        ]
    )


def _video_filters(
    width: Optional[int],
    height: Optional[int],
    fps: Optional[float],
    fit: str,
    transformations: Optional[Dict[str, Any]] = None,
) -> List[str]:
    filters = []
    if width and height:
        if fit == "cover":
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
    if transformations:
        orientation = str(transformations.get("orientation") or "normal")
        if orientation == "mirror_horizontal":
            filters.append("hflip")
        elif orientation != "normal":
            raise FFmpegError(f"Unsupported orientation: {orientation}")

        filters.extend(
            _motion_style_filters(
                str(transformations.get("motion_style") or "none"),
                width=width,
                height=height,
            )
        )

        preset_filters, preset_eq = _visual_style_filters(
            str(transformations.get("visual_style") or "natural")
        )
        filters.extend(preset_filters)

        eq_parts = preset_eq
        brightness = transformations.get("brightness")
        contrast = transformations.get("contrast")
        saturation = transformations.get("saturation")
        if brightness is not None:
            eq_parts["brightness"] = _bounded_float(brightness, -1.0, 1.0)
        if contrast is not None:
            eq_parts["contrast"] = _bounded_float(contrast, 0.0, 3.0)
        if saturation is not None:
            eq_parts["saturation"] = _bounded_float(saturation, 0.0, 3.0)
        if eq_parts:
            filters.append(
                "eq="
                + ":".join(f"{key}={value}" for key, value in eq_parts.items())
            )

        filters.extend(
            _finishing_style_filters(str(transformations.get("finishing_style") or "none"))
        )
        filters.extend(
            _texture_style_filters(str(transformations.get("texture_style") or "none"))
        )
        filters.extend(
            _transition_style_filters(str(transformations.get("transition_style") or "hard_cut"))
        )

        playback_speed = transformations.get("playback_speed")
        if playback_speed is not None:
            speed = _bounded_float(playback_speed, 0.5, 2.0)
            filters.append(f"setpts={1 / speed:.6f}*PTS")

        for region in transformations.get("cover_regions") or []:
            filters.append(_drawbox_filter(region))

        for overlay in transformations.get("text_overlays") or []:
            filters.append(_drawtext_filter(overlay))
    if fps:
        filters.append(f"fps={fps}")
    return filters


def _motion_style_filters(style: str, width: Optional[int], height: Optional[int]) -> List[str]:
    if style == "none":
        return []
    if style == "light_rotate":
        return ["rotate=0.015*sin(2*PI*t/3):fillcolor=black"]
    if style == "social_pulse":
        return ["rotate=0.006*sin(2*PI*t*4):fillcolor=black"]
    if width is None or height is None:
        raise FFmpegError(f"motion_style {style} requires fixed output width and height")
    if style == "slow_push_in":
        return [
            "scale=trunc(iw*1.06/2)*2:trunc(ih*1.06/2)*2",
            f"crop={width}:{height}:(in_w-out_w)/2:(in_h-out_h)/2",
        ]
    if style == "slow_pan":
        return [
            "scale=trunc(iw*1.08/2)*2:trunc(ih*1.08/2)*2",
            f"crop={width}:{height}:(in_w-out_w)*(0.5+0.5*sin(2*PI*t/4)):(in_h-out_h)/2",
        ]
    raise FFmpegError(f"Unsupported motion_style: {style}")


def _visual_style_filters(style: str) -> tuple[List[str], Dict[str, float]]:
    if style == "natural":
        return [], {}
    if style == "clean_ad":
        return ["unsharp=5:5:0.45:3:3:0.2"], {
            "brightness": 0.02,
            "contrast": 1.08,
            "saturation": 1.08,
        }
    if style == "warm_lifestyle":
        return ["hue=h=4:s=1.04"], {
            "brightness": 0.03,
            "contrast": 1.04,
            "saturation": 1.12,
        }
    if style == "cool_tech":
        return ["hue=h=-5:s=0.98", "unsharp=5:5:0.35:3:3:0.15"], {
            "brightness": 0.0,
            "contrast": 1.12,
            "saturation": 0.98,
        }
    if style == "punchy_social":
        return ["unsharp=5:5:0.6:3:3:0.25"], {
            "brightness": 0.015,
            "contrast": 1.18,
            "saturation": 1.25,
        }
    if style == "soft_beauty":
        return ["gblur=sigma=0.25"], {
            "brightness": 0.04,
            "contrast": 0.96,
            "saturation": 1.05,
        }
    raise FFmpegError(f"Unsupported visual_style: {style}")


def _finishing_style_filters(style: str) -> List[str]:
    if style == "none":
        return []
    if style == "sharpen":
        return ["unsharp=5:5:0.7:3:3:0.25"]
    if style == "soften":
        return ["gblur=sigma=0.45"]
    if style == "film_grain":
        return ["noise=alls=8:allf=t+u"]
    if style == "vignette":
        return ["vignette=PI/5"]
    raise FFmpegError(f"Unsupported finishing_style: {style}")


def _texture_style_filters(style: str) -> List[str]:
    if style == "none":
        return []
    if style == "warm_light_leak":
        return [
            "drawbox=x=0:y=0:w=iw:h=ih:color=orange@0.08:t=fill",
            "drawbox=x=0:y=0:w=iw*0.32:h=ih:color=yellow@0.06:t=fill",
        ]
    if style == "cool_light_leak":
        return [
            "drawbox=x=0:y=0:w=iw:h=ih:color=blue@0.06:t=fill",
            "drawbox=x=iw*0.68:y=0:w=iw*0.32:h=ih:color=cyan@0.05:t=fill",
        ]
    if style == "subtle_grid":
        return ["drawgrid=width=80:height=80:thickness=1:color=white@0.08"]
    raise FFmpegError(f"Unsupported texture_style: {style}")


def _transition_style_filters(style: str) -> List[str]:
    if style == "hard_cut":
        return []
    if style == "flash_white":
        return ["fade=t=in:st=0:d=0.10:color=white"]
    if style == "flash_black":
        return ["fade=t=in:st=0:d=0.10:color=black"]
    if style == "soft_fade":
        return ["fade=t=in:st=0:d=0.18:color=black"]
    raise FFmpegError(f"Unsupported transition_style: {style}")


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
        f"x={_non_negative_int(overlay.get('x'), 'text_overlays.x')}",
        f"y={_non_negative_int(overlay.get('y'), 'text_overlays.y')}",
        f"fontsize={_positive_int(overlay.get('font_size') or 54, 'text_overlays.font_size')}",
        f"fontcolor={_filter_value(overlay.get('font_color') or 'white')}",
    ]
    if box_color:
        parts.extend(
            [
                "box=1",
                f"boxcolor={_filter_value(box_color)}",
                f"boxborderw={_non_negative_int(overlay.get('box_padding') or 0, 'text_overlays.box_padding')}",
            ]
        )
    return ":".join(parts)


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
