BLUEPRINTS = {
    "problem_demo_cta_v1": {
        "blueprint_id": "problem_demo_cta_v1",
        "name": "Problem demo CTA",
        "creative_goal": {
            "title": "Problem demo CTA",
            "audience": "cold traffic",
            "selling_points": ["clear user pain", "human-shot product demo", "direct CTA"],
            "tone": "direct-response",
        },
        "production_contract": {
            "use_case": "First-pass performance ad from rights-cleared UGC footage.",
            "operator_notes": "Use when the source has a visible problem moment followed by product use. Source material is assumed rights-cleared before upload.",
            "review_checklist": [
                "Opening seconds communicate the problem.",
                "Product action remains visible after the hook.",
                "CTA does not imply unsupported claims.",
            ],
        },
        "editing": {
            "cut_style": "fixed_interval",
            "clip_duration_seconds": 2.5,
            "target_duration_seconds": 10.0,
            "max_clip_count": 4,
            "pacing": "fast",
            "keep_original_order": True,
        },
        "slots": [
            {
                "slot": "hook",
                "role": "source_segment",
                "min_duration_seconds": 2,
                "max_duration_seconds": 4,
                "notes": "Problem or attention cue.",
            },
            {
                "slot": "demo",
                "role": "source_segment",
                "min_duration_seconds": 4,
                "max_duration_seconds": 8,
                "notes": "Visible product use.",
            },
            {
                "slot": "cta",
                "role": "copy_pack",
                "optional": True,
            },
        ],
    },
    "testimonial_proof_v1": {
        "blueprint_id": "testimonial_proof_v1",
        "name": "Testimonial proof",
        "creative_goal": {
            "title": "Testimonial proof",
            "audience": "warm traffic",
            "selling_points": ["human reaction", "trust signal", "simple takeaway"],
            "tone": "credible",
        },
        "production_contract": {
            "use_case": "Trust-building variant when the source includes a face, reaction, or spoken proof moment.",
            "operator_notes": "Use only when the source person is already cleared for ad use before upload.",
            "review_checklist": [
                "Face or reaction remains visible and respectful.",
                "Caption does not imply unsupported claims.",
                "The person fits the intended ad context.",
            ],
        },
        "editing": {
            "cut_style": "fixed_interval",
            "clip_duration_seconds": 2.5,
            "target_duration_seconds": 10.0,
            "max_clip_count": 4,
            "pacing": "medium",
            "keep_original_order": True,
        },
        "slots": [
            {"slot": "hook", "role": "source_segment", "min_duration_seconds": 2},
            {"slot": "proof", "role": "source_segment", "min_duration_seconds": 4},
            {"slot": "cta", "role": "copy_pack", "optional": True},
        ],
    },
    "unboxing_steps_v1": {
        "blueprint_id": "unboxing_steps_v1",
        "name": "Unboxing setup steps",
        "creative_goal": {
            "title": "Unboxing setup steps",
            "audience": "new prospects",
            "selling_points": ["simple setup", "hands-on proof", "low friction"],
            "tone": "helpful",
        },
        "production_contract": {
            "use_case": "Step-by-step cutdown when source footage shows unpacking, setup, or first use.",
            "operator_notes": "Use when the source sequence has a clear beginning, middle, and end. Source material is assumed rights-cleared before upload.",
            "review_checklist": [
                "Setup sequence is understandable without extra explanation.",
                "Caption does not hide hands or key components.",
                "Final moment shows the product ready or in use.",
            ],
        },
        "editing": {
            "cut_style": "fixed_interval",
            "clip_duration_seconds": 2.0,
            "target_duration_seconds": 10.0,
            "max_clip_count": 5,
            "pacing": "medium",
            "keep_original_order": True,
        },
        "slots": [
            {"slot": "step_1", "role": "source_segment", "min_duration_seconds": 2},
            {"slot": "step_2", "role": "source_segment", "min_duration_seconds": 2},
            {"slot": "ready_state", "role": "source_segment", "min_duration_seconds": 2},
        ],
    },
}


RENDER_PRESETS = {
    "vertical_9_16_cover": {
        "preset_id": "vertical_9_16_cover",
        "name": "Vertical 9:16 cover",
        "delivery": {
            "aspect_ratio": "9:16",
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
            "format": "mp4",
            "fit": "cover",
        },
    },
    "vertical_9_16_contain": {
        "preset_id": "vertical_9_16_contain",
        "name": "Vertical 9:16 contain",
        "delivery": {
            "aspect_ratio": "9:16",
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
            "format": "mp4",
            "fit": "contain",
        },
    },
    "square_1_1_contain": {
        "preset_id": "square_1_1_contain",
        "name": "Square 1:1 contain",
        "delivery": {
            "aspect_ratio": "1:1",
            "width": 1080,
            "height": 1080,
            "fps": 30.0,
            "format": "mp4",
            "fit": "contain",
        },
    },
    "source_control_720p": {
        "preset_id": "source_control_720p",
        "name": "Source control 720p",
        "delivery": {
            "aspect_ratio": "source",
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "format": "mp4",
            "fit": "contain",
        },
    },
}


STYLE_PACKS = {
    "clean_ad": {
        "style_pack_id": "clean_ad",
        "name": "Clean ad",
        "transformations": {
            "orientation": "normal",
            "visual_style": "clean_ad",
            "finishing_style": "sharpen",
            "motion_style": "slow_push_in",
            "transition_style": "flash_white",
            "texture_style": "none",
            "brightness": 0.03,
            "contrast": 1.12,
            "saturation": 1.16,
            "playback_speed": 1.04,
            "volume": 0.95,
        },
    },
    "punchy_social": {
        "style_pack_id": "punchy_social",
        "name": "Punchy social",
        "transformations": {
            "orientation": "mirror_horizontal",
            "visual_style": "punchy_social",
            "finishing_style": "film_grain",
            "motion_style": "social_pulse",
            "transition_style": "flash_white",
            "texture_style": "warm_light_leak",
            "brightness": 0.05,
            "contrast": 1.32,
            "saturation": 1.3,
            "playback_speed": 1.18,
            "volume": 0.9,
        },
    },
    "natural_control": {
        "style_pack_id": "natural_control",
        "name": "Natural control",
        "transformations": {
            "orientation": "normal",
            "visual_style": "natural",
            "finishing_style": "none",
            "motion_style": "none",
            "transition_style": "hard_cut",
            "texture_style": "none",
            "brightness": 0.01,
            "contrast": 1.06,
            "saturation": 1.05,
            "volume": 0.98,
        },
    },
    "soft_proof": {
        "style_pack_id": "soft_proof",
        "name": "Soft proof",
        "transformations": {
            "orientation": "normal",
            "visual_style": "soft_beauty",
            "finishing_style": "soften",
            "motion_style": "light_rotate",
            "transition_style": "soft_fade",
            "texture_style": "none",
            "brightness": 0.02,
            "contrast": 1.04,
            "saturation": 1.0,
            "volume": 1.0,
        },
    },
}


COPY_PACKS = {
    "see_the_fix_cta": {
        "copy_pack_id": "see_the_fix_cta",
        "name": "See the fix CTA",
        "cover_regions": [
            {"x": 64, "y": 1540, "width": 952, "height": 210, "color": "black@0.76"}
        ],
        "text_overlays": [
            {
                "text": "SEE THE FIX",
                "x": 96,
                "y": 1592,
                "font_size": 62,
                "font_color": "white",
                "box_color": "black@0.0",
                "box_padding": 0,
            }
        ],
        "review_checklist": ["CTA overlay is readable on mobile."],
    },
    "three_sec_proof": {
        "copy_pack_id": "three_sec_proof",
        "name": "Three second proof",
        "cover_regions": [
            {"x": 72, "y": 108, "width": 936, "height": 172, "color": "red@0.70"}
        ],
        "text_overlays": [
            {
                "text": "3 SEC PROOF",
                "x": 104,
                "y": 146,
                "font_size": 70,
                "font_color": "white",
                "box_color": "black@0.0",
                "box_padding": 0,
            }
        ],
        "review_checklist": ["Proof banner does not cover key product action."],
    },
    "proof_in_action_square": {
        "copy_pack_id": "proof_in_action_square",
        "name": "Proof in action square",
        "text_overlays": [
            {
                "text": "PROOF IN ACTION",
                "x": 104,
                "y": 878,
                "font_size": 50,
                "font_color": "black",
                "box_color": "white@0.86",
                "box_padding": 20,
            }
        ],
        "review_checklist": ["Proof overlay is readable on feed preview."],
    },
    "steps_caption": {
        "copy_pack_id": "steps_caption",
        "name": "Steps caption",
        "text_overlays": [
            {
                "text": "STEP 1 -> STEP 2",
                "x": 86,
                "y": 132,
                "font_size": 52,
                "font_color": "white",
                "box_color": "black@0.72",
                "box_padding": 18,
            }
        ],
        "review_checklist": ["Step caption does not hide hands or key components."],
    },
}


RECOMMENDED_RECIPES = [
    {
        "name": "prod_problem_demo_cta_vertical_clean",
        "description": "Reusable problem-demo-CTA recipe using vertical clean-ad treatment.",
        "recipe_id": "problem_demo_cta.vertical.clean.see_the_fix",
        "blueprint_id": "problem_demo_cta_v1",
        "render_preset_id": "vertical_9_16_cover",
        "style_pack_id": "clean_ad",
        "copy_pack_id": "see_the_fix_cta",
        "review_notes": "Confirm pain clarity, demo visibility, CTA readability, and fit for pre-cleared source use.",
    },
    {
        "name": "prod_problem_demo_fast_hook_vertical",
        "description": "Fast hook/proof recipe for first-screen scroll-stopping tests.",
        "recipe_id": "problem_demo_cta.vertical.punchy.three_sec_proof",
        "blueprint_id": "problem_demo_cta_v1",
        "render_preset_id": "vertical_9_16_cover",
        "style_pack_id": "punchy_social",
        "copy_pack_id": "three_sec_proof",
        "slot_bindings": {
            "hook": {
                "source_type": "ai_asset",
                "asset_type": "hook",
                "tags": ["hook", "proof"],
                "duration": [2, 4],
                "optional": True,
            }
        },
        "review_notes": "Check first-frame hook, subject crop, proof clarity, and suitability for pre-cleared trial material.",
    },
    {
        "name": "prod_problem_demo_source_control",
        "description": "Control recipe with source framing and natural style.",
        "recipe_id": "problem_demo_cta.source.control.no_overlay",
        "blueprint_id": "problem_demo_cta_v1",
        "render_preset_id": "source_control_720p",
        "style_pack_id": "natural_control",
        "review_notes": "Use as the production control: check source message clarity and output quality.",
    },
    {
        "name": "prod_testimonial_square_proof",
        "description": "Square testimonial proof recipe for feed placements.",
        "recipe_id": "testimonial_proof.square.soft.proof_in_action",
        "blueprint_id": "testimonial_proof_v1",
        "render_preset_id": "square_1_1_contain",
        "style_pack_id": "soft_proof",
        "copy_pack_id": "proof_in_action_square",
        "review_notes": "Confirm square crop, proof readability, and testimonial claim safety.",
    },
    {
        "name": "prod_testimonial_vertical_contain",
        "description": "Vertical contain-fit testimonial recipe with low crop risk.",
        "recipe_id": "testimonial_proof.vertical_contain.soft.no_overlay",
        "blueprint_id": "testimonial_proof_v1",
        "render_preset_id": "vertical_9_16_contain",
        "style_pack_id": "soft_proof",
        "review_notes": "Check face visibility, claim safety, and whether the reaction reads clearly on mobile.",
    },
    {
        "name": "prod_unboxing_steps_vertical",
        "description": "Vertical unboxing/setup recipe with reusable step caption.",
        "recipe_id": "unboxing_steps.vertical.clean.steps_caption",
        "blueprint_id": "unboxing_steps_v1",
        "render_preset_id": "vertical_9_16_cover",
        "style_pack_id": "clean_ad",
        "copy_pack_id": "steps_caption",
        "review_notes": "Check setup clarity, component visibility, and whether the sequence feels complete.",
    },
]


def recipe_spec(recipe: dict) -> dict:
    spec = {
        "schema_version": 2,
        "type": "variant_recipe",
        "recipe_id": recipe["recipe_id"],
        "name": recipe["name"],
        "blueprint": BLUEPRINTS[recipe["blueprint_id"]],
        "render_preset": RENDER_PRESETS[recipe["render_preset_id"]],
        "style_pack": STYLE_PACKS[recipe["style_pack_id"]],
        "slot_bindings": recipe.get("slot_bindings", {}),
        "review_notes": recipe["review_notes"],
    }
    copy_pack_id = recipe.get("copy_pack_id")
    if copy_pack_id:
        spec["copy_pack"] = COPY_PACKS[copy_pack_id]
    return spec


PRODUCTION_TEMPLATES = [
    {
        "name": recipe["name"],
        "description": recipe["description"],
        "json_spec": recipe_spec(recipe),
    }
    for recipe in RECOMMENDED_RECIPES
]


V3_PRODUCTION_TEMPLATES = [
    {
        "name": "prod_v3_vertical_intro_outro_frame",
        "description": "v3 reusable method: vertical output with optional intro/outro clips and a required frame image slot.",
        "json_spec": {
            "schema_version": 3,
            "type": "video_modification_template",
            "template_id": "vertical_intro_outro_frame_v1",
            "name": "竖版前后贴片 + 图片框",
            "category": "packaging",
            "use_case": "批量把种子视频包装成统一品牌广告素材",
            "input_requirements": {
                "min_seed_duration_seconds": 3,
                "accepted_seed_ratios": ["9:16", "1:1", "16:9", "original"],
                "requires_audio": False,
            },
            "operations": [
                {
                    "type": "prepend_clip",
                    "slot": "intro",
                    "label": "前贴片",
                    "required": False,
                },
                {
                    "type": "resize_canvas",
                    "output_preset_id": "vertical_9_16_cover",
                },
                {
                    "type": "overlay_frame",
                    "slot": "frame_image",
                    "label": "图片框",
                    "placement": "full_canvas",
                    "required": True,
                },
                {
                    "type": "append_clip",
                    "slot": "outro",
                    "label": "后贴片",
                    "required": False,
                },
            ],
            "runtime_fields": [
                {
                    "key": "intro",
                    "label": "前贴片",
                    "field_type": "asset",
                    "asset_kind": "video",
                    "asset_type": "intro",
                    "required": False,
                },
                {
                    "key": "frame_image",
                    "label": "图片框",
                    "field_type": "asset",
                    "asset_kind": "image",
                    "asset_type": "frame",
                    "required": True,
                },
                {
                    "key": "outro",
                    "label": "后贴片",
                    "field_type": "asset",
                    "asset_kind": "video",
                    "asset_type": "outro",
                    "required": False,
                },
            ],
            "output_preset_id": "vertical_9_16_cover",
            "review_checklist": [
                "前贴片播放完整且不突兀",
                "图片框没有遮挡主体和关键信息",
                "后贴片 CTA 清晰",
                "成片无黑边、无异常裁切",
            ],
        },
    },
    {
        "name": "prod_v3_brand_watermark_caption_zone",
        "description": "v3 reusable method: vertical brand watermark and replaceable campaign headline.",
        "json_spec": {
            "schema_version": 3,
            "type": "video_modification_template",
            "template_id": "brand_watermark_caption_zone_v1",
            "name": "统一品牌水印 + 字幕安全区",
            "category": "brand_packaging",
            "use_case": "把一批素材统一加品牌标识和字幕底栏",
            "operations": [
                {
                    "type": "resize_canvas",
                    "output_preset_id": "vertical_9_16_contain",
                },
                {
                    "type": "overlay_logo",
                    "slot": "logo",
                    "label": "品牌 Logo",
                    "position": "top_right",
                    "safe_margin": 48,
                    "required": True,
                },
                {
                    "type": "cover_region",
                    "region": "bottom_caption_zone",
                    "color": "black@0.68",
                },
                {
                    "type": "text_placeholder",
                    "field": "campaign_headline",
                    "label": "活动主文案",
                    "region": "bottom_caption_zone",
                    "style": "mobile_readable",
                },
            ],
            "runtime_fields": [
                {
                    "key": "logo",
                    "label": "品牌 Logo",
                    "field_type": "asset",
                    "asset_kind": "image",
                    "asset_type": "logo",
                    "required": True,
                },
                {
                    "key": "campaign_headline",
                    "label": "本次活动文案",
                    "field_type": "text",
                    "max_length": 30,
                    "required": False,
                },
            ],
            "output_preset_id": "vertical_9_16_contain",
            "review_checklist": [
                "Logo 没有遮挡人物或产品主体",
                "底栏文案在手机上可读",
                "原视频主体完整保留",
            ],
        },
    },
]


BUILTIN_TEMPLATES = [*PRODUCTION_TEMPLATES, *V3_PRODUCTION_TEMPLATES]
