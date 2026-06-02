# Template System v3 设计文档：操作流程版

## 1. 背景

Flashcutter 当前模板 v2 已经把完整模板拆成：

```text
Blueprint + Slot Bindings + Render Preset + Style Pack + Copy Pack + Music Policy
```

v2 解决了模板组合条件过多的问题，但模板管理对设计/运营人员仍然不够直观：

```text
1. 模板仍像数据结构，不像一个可复用的视频修改方法。
2. 一次性营销文字和可复用制作规则混在一起。
3. 视频尺寸仍容易暴露为 width / height / fit 等工程字段。
4. 当前核心流程偏向“一个种子视频 + 多模板”，还缺少“一批视频 + 一个模板”的批处理视角。
5. 多视频 x 多模板的组合矩阵需要预检、回溯和失败重试能力。
```

v3 的目标不是增加更多模板字段，而是把模板系统重新组织成设计/运营人员能理解的生产工具。

---

## 2. v3 核心定位

v3 模板不再表示“某个具体广告变体配置”，而表示：

> **一个可复用的视频修改方法。**

模板负责回答：

```text
这个视频要怎么被改？
```

批次负责回答：

```text
这次用哪些视频？
这次用哪些前贴片、后贴片、图片框、Logo、文案和配乐？
这次生成哪些组合？
```

---

## 3. 核心边界

### 3.1 模板内保留可复用规则

模板可以包含：

```text
1. 前贴片规则
2. 后贴片规则
3. 视频叠加图片框规则
4. Logo / 水印规则
5. 尺寸适配规则
6. 裁切与留白策略
7. 音乐替换策略
8. 固定遮罩区域
9. 可复用字幕区域
10. 审核检查项
```

### 3.2 批次参数承载一次性内容

模板不保存：

```text
1. 某次活动文案
2. 某个价格
3. 某个产品名
4. 一次性 CTA
5. 本次指定的前贴片文件
6. 本次指定的后贴片文件
7. 本次指定的图片框文件
8. 某个具体种子视频 id
```

这些进入 `production_run.params_json` 或任务级 `params_json`。

### 3.3 输出尺寸使用预设

用户不能单独选择宽和高。

用户选择：

```text
竖版 9:16
方版 1:1
横版 16:9
保持原比例
```

系统内部映射：

```json
{
  "preset_id": "vertical_9_16_cover",
  "label": "竖版 9:16",
  "width": 1080,
  "height": 1920,
  "fit": "cover",
  "fps": 30,
  "format": "mp4"
}
```

---

## 4. v3 核心对象

### 4.1 Modification Template

可复用的视频修改方法。

```json
{
  "schema_version": 3,
  "type": "video_modification_template",
  "template_id": "vertical_intro_outro_frame_v1",
  "name": "竖版前后贴片 + 图片框",
  "category": "packaging",
  "use_case": "批量把种子视频包装成统一品牌广告素材",
  "input_requirements": {
    "min_seed_duration_seconds": 3,
    "accepted_seed_ratios": ["9:16", "1:1", "16:9", "original"],
    "requires_audio": false
  },
  "operations": [],
  "runtime_fields": [],
  "output_preset_id": "vertical_9_16_cover",
  "review_checklist": []
}
```

### 4.2 Operation

模板中的一个可复用修改步骤。

第一版支持以下操作：

```text
prepend_clip       前贴片
append_clip        后贴片
overlay_image      图片叠加
overlay_frame      图片框叠加
overlay_logo       Logo / 水印
cover_region       遮盖原画面区域
text_placeholder   可替换文字占位
replace_music      替换配乐
resize_canvas      输出规格适配
trim_seed          截取种子视频
```

示例：

```json
{
  "type": "prepend_clip",
  "slot": "intro",
  "label": "前贴片",
  "required": false,
  "fit": "match_output",
  "audio_policy": "keep_or_duck_seed"
}
```

### 4.3 Runtime Field

批次创建时需要运营填写的内容。

```json
{
  "key": "intro",
  "label": "前贴片",
  "field_type": "asset",
  "asset_kind": "video",
  "asset_type": "intro",
  "required": false
}
```

一次性文字使用 `text` 字段：

```json
{
  "key": "campaign_headline",
  "label": "活动主文案",
  "field_type": "text",
  "max_length": 30,
  "required": false
}
```

### 4.4 Output Preset

输出规格预设。

```json
{
  "preset_id": "vertical_9_16_cover",
  "label": "竖版 9:16",
  "description": "适合 TikTok / 抖音 / Reels 信息流。",
  "aspect_ratio": "9:16",
  "width": 1080,
  "height": 1920,
  "fit": "cover",
  "fps": 30,
  "format": "mp4"
}
```

推荐内置预设：

```text
vertical_9_16_cover       竖版 9:16，填满画面
vertical_9_16_contain     竖版 9:16，保留完整原画
square_1_1_contain        方版 1:1，保留完整原画
horizontal_16_9_cover     横版 16:9，填满画面
source_original           保持原尺寸
```

---

## 5. 模板类型

模板管理页不按 schema 字段组织，而按用途组织。

### 5.1 前后贴片模板

用于：

```text
给原视频前面加品牌开场
给原视频后面加 CTA / 活动结尾
```

典型操作：

```text
prepend_clip
append_clip
replace_music
resize_canvas
```

### 5.2 图片框模板

用于：

```text
给视频套手机框、产品框、品牌框、评价框
```

典型操作：

```text
overlay_frame
resize_canvas
cover_region
```

### 5.3 品牌包装模板

用于：

```text
统一 Logo、水印、品牌色、字幕安全区
```

典型操作：

```text
overlay_logo
cover_region
text_placeholder
replace_music
```

### 5.4 尺寸适配模板

用于：

```text
把一批素材批量转成平台规格
```

典型操作：

```text
resize_canvas
trim_seed
replace_music
```

---

## 6. 示例模板

### 6.1 竖版前后贴片 + 图片框

```json
{
  "schema_version": 3,
  "type": "video_modification_template",
  "template_id": "vertical_intro_outro_frame_v1",
  "name": "竖版前后贴片 + 图片框",
  "category": "packaging",
  "use_case": "批量把种子视频包装成统一品牌广告素材",
  "operations": [
    {
      "type": "prepend_clip",
      "slot": "intro",
      "label": "前贴片",
      "required": false
    },
    {
      "type": "resize_canvas",
      "output_preset_id": "vertical_9_16_cover"
    },
    {
      "type": "overlay_frame",
      "slot": "frame_image",
      "label": "图片框",
      "placement": "full_canvas",
      "required": true
    },
    {
      "type": "append_clip",
      "slot": "outro",
      "label": "后贴片",
      "required": false
    }
  ],
  "runtime_fields": [
    {
      "key": "intro",
      "label": "前贴片",
      "field_type": "asset",
      "asset_kind": "video",
      "asset_type": "intro",
      "required": false
    },
    {
      "key": "frame_image",
      "label": "图片框",
      "field_type": "asset",
      "asset_kind": "image",
      "asset_type": "frame",
      "required": true
    },
    {
      "key": "outro",
      "label": "后贴片",
      "field_type": "asset",
      "asset_kind": "video",
      "asset_type": "outro",
      "required": false
    }
  ],
  "output_preset_id": "vertical_9_16_cover",
  "review_checklist": [
    "前贴片播放完整且不突兀",
    "图片框没有遮挡主体和关键信息",
    "后贴片 CTA 清晰",
    "成片无黑边、无异常裁切"
  ]
}
```

### 6.2 统一品牌包装

```json
{
  "schema_version": 3,
  "type": "video_modification_template",
  "template_id": "brand_watermark_caption_zone_v1",
  "name": "统一品牌水印 + 字幕安全区",
  "category": "brand_packaging",
  "use_case": "把一批素材统一加品牌标识和字幕底栏",
  "operations": [
    {
      "type": "resize_canvas",
      "output_preset_id": "vertical_9_16_contain"
    },
    {
      "type": "overlay_logo",
      "slot": "logo",
      "position": "top_right",
      "safe_margin": 48,
      "required": true
    },
    {
      "type": "cover_region",
      "region": "bottom_caption_zone",
      "color": "black@0.68"
    },
    {
      "type": "text_placeholder",
      "field": "campaign_headline",
      "region": "bottom_caption_zone",
      "style": "mobile_readable"
    }
  ],
  "runtime_fields": [
    {
      "key": "logo",
      "label": "品牌 Logo",
      "field_type": "asset",
      "asset_kind": "image",
      "asset_type": "logo",
      "required": true
    },
    {
      "key": "campaign_headline",
      "label": "本次活动文案",
      "field_type": "text",
      "max_length": 30,
      "required": false
    }
  ],
  "output_preset_id": "vertical_9_16_contain",
  "review_checklist": [
    "Logo 没有遮挡人物或产品主体",
    "底栏文案在手机上可读",
    "原视频主体完整保留"
  ]
}
```

---

## 7. 三种生产流程

### 7.1 单种子视频，多模板

当前主流程。

```text
选择 1 个种子视频
选择多个模板
填写批次参数
预检
生成多个变体
进入审核
```

适合：

```text
同一个视频测试多种包装方式
同一条素材快速做多平台规格
```

任务数量：

```text
1 个视频 x N 个模板
```

### 7.2 多种子视频，单模板

v3 必须新增的核心流程。

```text
选择一批视频
选择 1 个模板
填写一次批次参数
预检每个视频的适配结果
批量入队
进入审核
```

适合：

```text
一批达人素材统一加品牌前后贴片
一批产品视频统一套图片框
一批素材统一转竖版规格
```

任务数量：

```text
N 个视频 x 1 个模板
```

### 7.3 多种子视频，多模板矩阵

高级流程。

```text
选择一批视频
选择多个模板
系统生成组合矩阵
预检任务数、缺失素材、裁切风险、重复组合
用户确认后入队
进入审核
```

适合：

```text
10 条素材 x 3 个包装模板 = 30 个衍生品
多个投放平台规格一次性生成
```

任务数量：

```text
N 个视频 x M 个模板
```

必须有预检，不允许直接静默创建大量任务。

---

## 8. 批次参数

批次参数是一次生产运行的上下文。

```json
{
  "production_mode": "many_assets_one_template",
  "asset_ids": [101, 102, 103],
  "template_ids": [20],
  "runtime_values": {
    "intro": {
      "asset_id": 501
    },
    "frame_image": {
      "asset_id": 601
    },
    "outro": {
      "asset_id": 502
    },
    "campaign_headline": "618 限时活动"
  },
  "output_preset_id": "vertical_9_16_cover",
  "name_prefix": "brand-frame-batch"
}
```

运行时参数的原则：

```text
1. 可以被同一个批次内所有任务复用。
2. 可以在失败后修改并重新发起。
3. 不污染模板本身。
4. 必须记录进 production_run，便于审核与复盘。
```

---

## 9. 预检设计

所有批量流程都必须先预检。

预检输出：

```text
1. 预计任务数
2. 每个任务的输入视频
3. 每个任务的模板
4. 输出规格
5. 前贴片/后贴片/图片框/Logo 是否齐全
6. 视频时长是否满足模板要求
7. 裁切或留白风险
8. 图片框尺寸是否匹配输出规格
9. 是否会替换音乐
10. 预计生成时长
```

预检状态：

```text
ready
warning
blocked
```

示例：

```json
{
  "summary": {
    "asset_count": 10,
    "template_count": 3,
    "task_count": 30,
    "ready_count": 28,
    "warning_count": 2,
    "blocked_count": 0
  },
  "items": [
    {
      "asset_id": 101,
      "template_id": 20,
      "status": "warning",
      "output_preset": "竖版 9:16",
      "operations": ["前贴片", "图片框", "后贴片"],
      "warnings": ["原视频是横版，竖版 cover 会裁切左右两侧。"],
      "missing_fields": []
    }
  ]
}
```

---

## 10. 失败回溯与重新发起

v3 生产运行必须把失败变成可操作状态。

失败信息不能只显示：

```text
Failed to fetch
Render failed
Invalid params
```

必须显示：

```text
当前处境
失败发生在哪一步
为什么失败
用户可以做什么
```

示例：

```text
这批任务没有入队
原因：模板“竖版前后贴片 + 图片框”缺少必填图片框。
你可以：
1. 返回上一步选择图片框
2. 改用不需要图片框的模板
3. 暂存这批配置，稍后继续
```

每个 `production_run` 应保留：

```text
original_request_json
validated_plan_json
failed_step
error_code
operator_message
retryable
created_task_ids
```

---

## 11. 后端 API 设计

### 11.1 获取模板列表

```http
GET /api/template-system/templates
```

返回运营友好字段：

```json
{
  "items": [
    {
      "template_id": 20,
      "name": "竖版前后贴片 + 图片框",
      "category": "packaging",
      "use_case": "批量把种子视频包装成统一品牌广告素材",
      "required_runtime_fields": ["图片框"],
      "optional_runtime_fields": ["前贴片", "后贴片"],
      "output_preset": "竖版 9:16",
      "recent_usage_count": 18
    }
  ]
}
```

### 11.2 创建模板

```http
POST /api/template-system/templates
```

### 11.3 校验模板

```http
POST /api/template-system/templates/validate
```

### 11.4 生产预检

```http
POST /api/production-runs/preflight
```

Request：

```json
{
  "asset_ids": [101, 102],
  "template_ids": [20, 21],
  "runtime_values": {
    "frame_image": {
      "asset_id": 601
    }
  },
  "output_preset_id": "vertical_9_16_cover",
  "name_prefix": "brand-frame-batch"
}
```

### 11.5 创建并入队

```http
POST /api/production-runs/enqueue
```

要求：

```text
必须传入最近一次 preflight_token 或 validated_plan_json。
不允许绕过预检直接创建大批量任务。
```

---

## 12. 编译器设计

新增：

```text
backend/app/services/template_v3_compiler.py
```

职责：

```text
1. 校验 v3 模板 schema。
2. 合并模板和 runtime_values。
3. 编译为现有 renderer 能执行的 CompiledTemplateSpec。
4. 生成前后贴片、图片框、Logo、文字占位等 operation plan。
5. 生成预检 warning / blocked 信息。
```

编译流程：

```text
Template v3
  + Runtime Values
  + Output Preset
  + Seed Asset Metadata
  -> Validated Production Plan
  -> Renderer Plan
```

第一阶段可以先把 v3 编译到现有 v2/内部 renderer spec，避免一次性重写渲染器。

---

## 13. 前端设计

### 13.1 模板管理页

路径建议：

```text
frontend/src/pages/TemplatesPage.tsx
```

重构为：

```text
模板列表
├── 类型筛选
│   ├── 前后贴片
│   ├── 图片框
│   ├── 品牌包装
│   └── 尺寸适配
│
├── 模板卡片
│   ├── 模板名称
│   ├── 适用场景
│   ├── 需要哪些素材
│   ├── 输出规格
│   └── 最近使用
│
└── 创建 / 编辑模板向导
    ├── 选择模板类型
    ├── 添加修改步骤
    ├── 设置需要填写的批次参数
    ├── 选择输出规格
    └── 设置审核检查项
```

模板编辑器不要默认展示 JSON。高级 JSON 只放到折叠区。

### 13.2 变体生产页

路径建议：

```text
frontend/src/pages/CreateVariantsPage.tsx
```

改成流程选择：

```text
我要：
1. 一个视频生成多版
2. 一批视频套同一个模板
3. 多个视频和多个模板组合生成
```

每种流程都在一个对话框内完成：

```text
选择视频
选择模板
填写批次参数
预检
入队
完成后提醒审核
```

### 13.3 批次参数表单

根据模板 `runtime_fields` 动态渲染：

```text
asset 字段 -> 资产选择器
text 字段 -> 文案输入框
boolean 字段 -> 开关
choice 字段 -> 单选/下拉
number 字段 -> 数值输入
```

---

## 14. 数据模型建议

### 14.1 templates

继续复用现有 `templates` 表，但 `json_spec` 支持 v3。

新增或派生字段可后续考虑：

```text
category
usage_count
last_used_at
```

第一阶段可从 `json_spec` 计算。

### 14.2 production_runs

建议补充：

```text
mode
asset_ids_json
template_ids_json
runtime_values_json
validated_plan_json
preflight_summary_json
failed_step
error_code
operator_message
retryable
```

第一阶段若不改表，可先放进现有 `params_json` 或新增 JSON 字段。

---

## 15. MVP 实施拆分

### PR 1：v3 文档与 schema

```text
docs/template_system_v3.md
Pydantic v3 schema
Output preset registry
Operation schema
Runtime field schema
```

### PR 2：v3 编译器与预检

```text
template_v3_compiler.py
生产矩阵展开
缺失字段检查
裁切风险检查
图片框匹配检查
```

### PR 3：批量生产 API

```text
POST /api/production-runs/preflight
POST /api/production-runs/enqueue
支持单视频多模板
支持多视频单模板
支持多视频多模板
```

### PR 4：模板管理页重构

```text
运营友好模板卡片
创建/编辑模板向导
输出规格预设选择
runtime_fields 表单配置
高级 JSON 折叠
```

### PR 5：变体生产页重构

```text
流程选择
批次参数动态表单
矩阵预检
失败回溯
重新发起
完成后审核提醒
```

### PR 6：渲染能力补齐

```text
前贴片 concat
后贴片 concat
图片框 overlay
Logo overlay
文字占位渲染
配乐替换
```

---

## 16. MVP 验收标准

v3 第一版完成后必须做到：

```text
1. 用户能创建一个“前后贴片 + 图片框”模板。
2. 用户选择输出规格时不能手填宽高。
3. 一次性活动文案不会写入模板，只写入批次参数。
4. 一个视频可以选择多个模板生成多个变体。
5. 多个视频可以选择一个模板批量生成。
6. 多个视频 x 多个模板可以预检组合矩阵。
7. 缺少前贴片/后贴片/图片框时，预检能明确提示。
8. 失败任务能回到原批次配置重新发起。
9. 模板管理页默认不展示 JSON。
10. 审核页仍能看到任务来自哪个视频、哪个模板、哪个批次。
```

---

## 17. 结论

v3 的产品方向是：

```text
模板 = 可复用的视频修改方法
批次参数 = 本次生产的一次性内容
输出规格 = 业务预设，不是宽高输入
生产 = 单视频多模板 / 多视频单模板 / 多视频多模板
```

这比继续扩展 v2 recipe 更适合设计/运营人员使用，也更贴近 Flashcutter 的核心生产场景：从一批真实、授权的视频素材中快速生成可审核、可复盘、可重试的广告衍生品。
