# Ad Variant Template v2

## 1. 目标

广告变体生产不再维护大量完整模板。v2 使用可组合配方：

```text
Variant Recipe = Blueprint + Slot Bindings + Render Preset + Style Pack + Copy Pack + Music Policy
```

系统只把推荐组合暴露给运营，不把所有可能条件做笛卡尔积。

---

## 2. 为什么改

旧模板同时绑定：

```text
广告意图
选段策略
画幅/尺寸/裁切
调色/动效/转场
字幕/遮挡/CTA
音乐
审核提示
```

这会导致 Hook x CTA x B-roll x 画幅 x 风格 x 音乐 每加一个条件就复制一个完整模板。v2 把这些维度拆开，提升复用性。

---

## 3. 核心对象

### 3.1 Blueprint

描述广告结构和运营语义，不绑定画幅或视觉风格。

```json
{
  "blueprint_id": "problem_demo_cta_v1",
  "name": "Problem demo CTA",
  "creative_goal": {
    "title": "Problem demo CTA",
    "audience": "cold traffic",
    "selling_points": ["clear user pain", "human-shot product demo", "direct CTA"],
    "tone": "direct-response"
  },
  "production_contract": {
    "use_case": "First-pass performance ad from rights-cleared UGC footage.",
    "operator_notes": "Use when the source has a visible problem moment followed by product use.",
    "review_checklist": [
      "Opening seconds communicate the problem.",
      "Product action remains visible after the hook."
    ]
  },
  "editing": {
    "cut_style": "fixed_interval",
    "clip_duration_seconds": 2.5,
    "target_duration_seconds": 10,
    "max_clip_count": 4,
    "pacing": "fast",
    "keep_original_order": true
  },
  "slots": [
    {
      "slot": "hook",
      "role": "source_segment",
      "min_duration_seconds": 2,
      "max_duration_seconds": 4
    },
    {
      "slot": "cta",
      "role": "copy_pack",
      "optional": true
    }
  ]
}
```

### 3.2 Render Preset

描述交付格式。

```json
{
  "preset_id": "vertical_9_16_cover",
  "name": "Vertical 9:16 cover",
  "delivery": {
    "aspect_ratio": "9:16",
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "format": "mp4",
    "fit": "cover"
  }
}
```

### 3.3 Style Pack

描述视觉处理。

```json
{
  "style_pack_id": "clean_ad",
  "name": "Clean ad",
  "transformations": {
    "visual_style": "clean_ad",
    "finishing_style": "sharpen",
    "motion_style": "slow_push_in",
    "transition_style": "flash_white",
    "brightness": 0.03,
    "contrast": 1.12,
    "saturation": 1.16
  }
}
```

### 3.4 Copy Pack

描述可复用文案、遮挡区域和文案审核点。

```json
{
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
      "font_color": "white"
    }
  ],
  "review_checklist": ["CTA overlay is readable on mobile."]
}
```

### 3.5 Variant Recipe

系统实际 seed 到 `templates` 表的是 recipe。

```json
{
  "schema_version": 2,
  "type": "variant_recipe",
  "recipe_id": "problem_demo_cta.vertical.clean.see_the_fix",
  "name": "prod_problem_demo_cta_vertical_clean",
  "blueprint": {},
  "render_preset": {},
  "style_pack": {},
  "copy_pack": {},
  "slot_bindings": {
    "hook": {
      "source_type": "ai_asset",
      "asset_type": "hook",
      "tags": ["hook", "proof"],
      "duration": [2, 4],
      "optional": true
    }
  },
  "review_notes": "Confirm pain clarity, demo visibility, CTA readability, and fit for pre-cleared source use."
}
```

---

## 4. 编译规则

`template_compiler.py` 把 v2 recipe 编译为 renderer 内部 spec：

```text
blueprint.creative_goal          -> creative_goal
blueprint.production_contract    -> production_contract
blueprint.editing                -> segments + selection
render_preset.delivery           -> output + layout
style_pack.transformations       -> transformations
copy_pack.cover_regions          -> transformations.cover_regions
copy_pack.text_overlays          -> transformations.text_overlays
copy_pack.review_checklist       -> production_contract.review_checklist
music                            -> music
```

当前 FFmpeg renderer 仍执行 source segment 拼接。`slot_bindings` 会进入 recipe 元数据，用于下一阶段接入 AI asset selection。

---

## 5. 运营原则

- 内置库只维护推荐 recipe，不维护全部组合。
- 新增广告叙事时加 Blueprint。
- 新增平台/画幅时加 Render Preset。
- 新增视觉处理时加 Style Pack。
- 新增 CTA 或字幕策略时加 Copy Pack。
- 新增可售卖变体组合时加 Recommended Recipe。

---

## 6. 当前内置模块

代码入口：

```text
backend/app/template_library.py
backend/app/services/template_compiler.py
```

当前 seed 的 recipe：

```text
prod_problem_demo_cta_vertical_clean
prod_problem_demo_fast_hook_vertical
prod_problem_demo_source_control
prod_testimonial_square_proof
prod_testimonial_vertical_contain
prod_unboxing_steps_vertical
```
