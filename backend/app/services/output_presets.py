from app.schemas import TemplateOutputPresetSpec


OUTPUT_PRESETS: dict[str, TemplateOutputPresetSpec] = {
    "vertical_9_16_cover": TemplateOutputPresetSpec(
        preset_id="vertical_9_16_cover",
        label="竖版 9:16",
        description="适合 TikTok / 抖音 / Reels 信息流，填满画面。",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        fit="cover",
        fps=30.0,
        format="mp4",
    ),
    "vertical_9_16_contain": TemplateOutputPresetSpec(
        preset_id="vertical_9_16_contain",
        label="竖版 9:16 保留完整画面",
        description="适合低裁切风险包装，保留原视频完整画面。",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        fit="contain",
        fps=30.0,
        format="mp4",
    ),
    "square_1_1_contain": TemplateOutputPresetSpec(
        preset_id="square_1_1_contain",
        label="方版 1:1",
        description="适合信息流方版素材，保留完整原画。",
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        fit="contain",
        fps=30.0,
        format="mp4",
    ),
    "horizontal_16_9_cover": TemplateOutputPresetSpec(
        preset_id="horizontal_16_9_cover",
        label="横版 16:9",
        description="适合横版平台，填满画面。",
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        fit="cover",
        fps=30.0,
        format="mp4",
    ),
    "source_original": TemplateOutputPresetSpec(
        preset_id="source_original",
        label="保持原尺寸",
        description="不改变原视频尺寸。",
        aspect_ratio="source",
        width=None,
        height=None,
        fit="original",
        fps=None,
        format="mp4",
    ),
}


def output_preset_for_id(preset_id: str) -> TemplateOutputPresetSpec:
    try:
        return OUTPUT_PRESETS[preset_id]
    except KeyError as exc:
        raise ValueError(f"Unknown output preset: {preset_id}") from exc
