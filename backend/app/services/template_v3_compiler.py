from typing import Any, Dict, List, Optional

from app.schemas import (
    CompiledTemplateSpec,
    TemplateCoverRegion,
    TemplateCreativeGoal,
    TemplateMusicSpec,
    TemplateProductionContract,
    TemplateSpecV3,
    TemplateTextOverlay,
    TemplateTransformationsSpec,
)
from app.services.output_presets import output_preset_for_id
from app.services.template_compiler import normalize_compiled_template_spec


DEFAULT_SEGMENT_SECONDS = 3.0
DEFAULT_MAX_CLIP_COUNT = 4


def compile_template_v3_spec(
    template: TemplateSpecV3, params_json: Optional[Dict[str, Any]] = None
) -> CompiledTemplateSpec:
    runtime_values = runtime_values_from_params(params_json)
    preset_id = (
        runtime_values.get("output_preset_id")
        or (params_json or {}).get("output_preset_id")
        or template.output_preset_id
    )
    delivery = output_preset_for_id(str(preset_id)).to_delivery()
    transformations = TemplateTransformationsSpec()

    music = TemplateMusicSpec()
    music_value = runtime_values.get("music")
    if isinstance(music_value, dict) and music_value.get("track_id"):
        music = music.model_copy(update=music_value)

    for operation in template.operations:
        if operation.type == "cover_region":
            transformations.cover_regions.append(
                cover_region_for_operation(operation.region, operation.color)
            )
        elif operation.type == "text_placeholder" and operation.field:
            text = runtime_values.get(operation.field)
            if isinstance(text, str) and text.strip():
                transformations.text_overlays.append(
                    text_overlay_for_operation(text=text.strip(), style=operation.style)
                )
        elif operation.type == "replace_music":
            track_id = runtime_values.get(operation.slot or "music")
            if isinstance(track_id, int):
                music = music.model_copy(update={"track_id": track_id})

    compiled = CompiledTemplateSpec(
        creative_goal=TemplateCreativeGoal(title=template.name),
        production_contract=TemplateProductionContract(
            use_case=template.use_case,
            operator_notes="按模板定义的视频修改步骤批量处理，具体素材与一次性文案来自生产批次参数。",
            review_checklist=template.review_checklist,
        ),
        delivery=delivery,
        music=music,
        transformations=transformations,
        review_notes="；".join(template.review_checklist) if template.review_checklist else None,
    )
    return normalize_compiled_template_spec(compiled)


def runtime_values_from_params(params_json: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(params_json, dict):
        return {}
    values = params_json.get("runtime_values")
    return values if isinstance(values, dict) else {}


def v3_required_runtime_fields(template: TemplateSpecV3) -> List[str]:
    return [field.key for field in template.runtime_fields if field.required]


def v3_missing_runtime_fields(
    template: TemplateSpecV3, runtime_values: Dict[str, Any]
) -> List[str]:
    missing = []
    for field in template.runtime_fields:
        if not field.required:
            continue
        value = runtime_values.get(field.key)
        if value in (None, "", []):
            missing.append(field.label)
            continue
        if field.field_type == "asset" and isinstance(value, dict) and not value.get("asset_id"):
            missing.append(field.label)
    return missing


def v3_operation_labels(template: TemplateSpecV3) -> List[str]:
    labels = []
    for operation in template.operations:
        if operation.label:
            labels.append(operation.label)
        elif operation.type == "prepend_clip":
            labels.append("前贴片")
        elif operation.type == "append_clip":
            labels.append("后贴片")
        elif operation.type in {"overlay_frame", "overlay_image"}:
            labels.append("图片叠加")
        elif operation.type == "overlay_logo":
            labels.append("Logo")
        elif operation.type == "resize_canvas":
            labels.append("输出规格")
    return labels


def cover_region_for_operation(region: Optional[str], color: Optional[str]) -> TemplateCoverRegion:
    if region == "opening_hook_zone":
        return TemplateCoverRegion(
            x=48,
            y=86,
            width=984,
            height=230,
            color=color or "black@0.54",
        )
    if region == "bottom_caption_zone":
        return TemplateCoverRegion(
            x=0,
            y=1540,
            width=1080,
            height=300,
            color=color or "black@0.68",
        )
    return TemplateCoverRegion(
        x=0,
        y=0,
        width=1080,
        height=160,
        color=color or "black@0.5",
    )


def text_overlay_for_operation(text: str, style: Optional[str]) -> TemplateTextOverlay:
    if style == "opening_hook":
        return TemplateTextOverlay(
            text=text,
            x=72,
            y=118,
            font_size=60,
            font_color="white",
            box_color="black@0.66",
            box_padding=20,
            start_sec=0,
            end_sec=3.2,
        )
    if style == "mobile_readable":
        return TemplateTextOverlay(
            text=text,
            x=72,
            y=1620,
            font_size=58,
            font_color="white",
            box_color="black@0.0",
            box_padding=0,
        )
    return TemplateTextOverlay(
        text=text,
        x=72,
        y=120,
        font_size=54,
        font_color="white",
        box_color="black@0.62",
        box_padding=18,
    )


def v3_runtime_asset_ids(params_json: Optional[Dict[str, Any]], slot_names: set[str]) -> Dict[str, int]:
    runtime_values = runtime_values_from_params(params_json)
    asset_ids = {}
    for slot in slot_names:
        value = runtime_values.get(slot)
        if isinstance(value, dict) and value.get("asset_id"):
            asset_ids[slot] = int(value["asset_id"])
        elif isinstance(value, int):
            asset_ids[slot] = value
    return asset_ids
