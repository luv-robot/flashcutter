from typing import Any, Dict, List, Optional

from app.schemas import (
    CompiledTemplateSpec,
    TemplateCopyPackSpec,
    TemplateSpec,
    TemplateTransformationsSpec,
)


def compile_template_spec(
    recipe: TemplateSpec, params_json: Optional[Dict[str, Any]] = None
) -> CompiledTemplateSpec:
    recipe = apply_recipe_overrides(recipe, params_json or {})
    transformations = merge_transformations(
        recipe.style_pack.transformations,
        recipe.copy_pack,
    )
    production_contract = recipe.blueprint.production_contract
    if recipe.copy_pack and recipe.copy_pack.review_checklist:
        production_contract = production_contract.model_copy(
            update={
                "review_checklist": [
                    *production_contract.review_checklist,
                    *recipe.copy_pack.review_checklist,
                ]
            }
        )

    compiled = CompiledTemplateSpec(
        creative_goal=recipe.blueprint.creative_goal.model_copy(
            update={
                "title": recipe.blueprint.creative_goal.title or recipe.name,
            }
        ),
        production_contract=production_contract,
        editing=recipe.blueprint.editing,
        delivery=recipe.render_preset.delivery,
        music=recipe.music,
        transformations=transformations,
        review_notes=recipe.review_notes,
    )
    return normalize_compiled_template_spec(compiled)


def apply_recipe_overrides(
    recipe: TemplateSpec, params_json: Dict[str, Any]
) -> TemplateSpec:
    recipe_params = params_json.get("recipe") if isinstance(params_json, dict) else None
    if not isinstance(recipe_params, dict):
        return recipe

    updates: Dict[str, Any] = {}
    if isinstance(recipe_params.get("slot_bindings"), dict):
        updates["slot_bindings"] = {
            **recipe.slot_bindings,
            **recipe_params["slot_bindings"],
        }
    if isinstance(recipe_params.get("music"), dict):
        updates["music"] = recipe.music.model_copy(update=recipe_params["music"])
    if isinstance(recipe_params.get("blueprint"), dict):
        updates["blueprint"] = recipe.blueprint.model_copy(
            update=recipe_params["blueprint"]
        )
    if isinstance(recipe_params.get("render_preset"), dict):
        updates["render_preset"] = recipe.render_preset.model_copy(
            update=recipe_params["render_preset"]
        )
    if isinstance(recipe_params.get("style_pack"), dict):
        updates["style_pack"] = recipe.style_pack.model_copy(
            update=recipe_params["style_pack"]
        )
    if isinstance(recipe_params.get("copy_pack"), dict):
        base_copy_pack = recipe.copy_pack or TemplateCopyPackSpec(
            copy_pack_id="inline",
            name="Inline copy pack",
        )
        updates["copy_pack"] = base_copy_pack.model_copy(
            update=recipe_params["copy_pack"]
        )
    if "review_notes" in recipe_params:
        updates["review_notes"] = recipe_params["review_notes"]

    return TemplateSpec.model_validate(recipe.model_copy(update=updates).model_dump())


def merge_transformations(
    style_transformations: TemplateTransformationsSpec,
    copy_pack: Optional[TemplateCopyPackSpec],
) -> TemplateTransformationsSpec:
    if copy_pack is None:
        return style_transformations
    return style_transformations.model_copy(
        update={
            "cover_regions": [
                *style_transformations.cover_regions,
                *copy_pack.cover_regions,
            ],
            "text_overlays": [
                *style_transformations.text_overlays,
                *copy_pack.text_overlays,
            ],
        }
    )


def normalize_compiled_template_spec(
    spec: CompiledTemplateSpec,
) -> CompiledTemplateSpec:
    if spec.editing is not None:
        spec = spec.model_copy(
            update={
                "segments": spec.segments.model_copy(
                    update={"segment_seconds": spec.editing.clip_duration_seconds}
                ),
                "selection": spec.selection.model_copy(
                    update={
                        "mode": "first_n"
                        if spec.editing.max_clip_count is not None
                        else spec.selection.mode,
                        "count": spec.editing.max_clip_count,
                        "max_total_duration": spec.editing.target_duration_seconds,
                    }
                ),
            }
        )

    if spec.delivery is not None:
        spec = spec.model_copy(
            update={
                "output": spec.output.model_copy(
                    update={
                        "width": spec.delivery.width,
                        "height": spec.delivery.height,
                        "fps": spec.delivery.fps,
                        "format": spec.delivery.format,
                    }
                ),
                "layout": spec.layout.model_copy(update={"fit": spec.delivery.fit}),
            }
        )

    return spec


def template_warnings(spec: CompiledTemplateSpec) -> List[str]:
    warnings = []
    if spec.delivery and spec.delivery.aspect_ratio != "source":
        if not spec.delivery.width or not spec.delivery.height:
            warnings.append("delivery.aspect_ratio is set but width/height are missing.")
    if spec.layout.fit in {"cover", "contain"} and (
        not spec.output.width or not spec.output.height
    ):
        warnings.append("cover/contain fit modes need output width and height.")
    if spec.selection.mode == "first_n" and not spec.selection.count:
        warnings.append("selection.mode first_n is easier to review with selection.count.")
    if not spec.creative_goal.title:
        warnings.append("blueprint.creative_goal.title helps reviewers understand the variant.")
    if not spec.review_notes:
        warnings.append("review_notes should describe the operator review focus.")
    if not spec.production_contract.review_checklist:
        warnings.append("blueprint.production_contract.review_checklist should guide reviewers.")
    if not spec.production_contract.use_case:
        warnings.append("blueprint.production_contract.use_case helps operators choose the recipe.")
    return warnings
