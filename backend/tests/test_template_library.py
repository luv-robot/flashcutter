from app.schemas import TemplateSpec
from app.services.template_compiler import compile_template_spec, template_warnings
from app.template_library import PRODUCTION_TEMPLATES


def test_production_recipes_are_valid_and_reviewable() -> None:
    assert len(PRODUCTION_TEMPLATES) >= 5

    names = set()
    for template in PRODUCTION_TEMPLATES:
        assert template["name"].startswith("prod_")
        assert template["name"] not in names
        names.add(template["name"])

        recipe = TemplateSpec.model_validate(template["json_spec"])
        spec = compile_template_spec(recipe)
        assert recipe.schema_version == 2
        assert recipe.type == "variant_recipe"
        assert recipe.blueprint.blueprint_id
        assert recipe.render_preset.preset_id
        assert recipe.style_pack.style_pack_id
        assert spec.creative_goal.title
        assert spec.review_notes
        assert spec.production_contract.use_case
        assert spec.production_contract.operator_notes
        assert spec.production_contract.review_checklist
        assert not template_warnings(spec)


def test_production_recipe_compiles_to_renderer_fields() -> None:
    template = next(
        item
        for item in PRODUCTION_TEMPLATES
        if item["name"] == "prod_problem_demo_cta_vertical_clean"
    )

    spec = compile_template_spec(TemplateSpec.model_validate(template["json_spec"]))

    assert spec.segments.segment_seconds == 2.5
    assert spec.selection.mode == "first_n"
    assert spec.selection.count == 4
    assert spec.selection.max_total_duration == 10.0
    assert spec.output.width == 1080
    assert spec.output.height == 1920
    assert spec.layout.fit == "cover"
    assert spec.transformations.text_overlays[0].text == "SEE THE FIX"
