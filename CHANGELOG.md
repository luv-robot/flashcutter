# Changelog

## 2026-05-13 — Visible variant features

### 背景

之前的 `transformations`（亮度 / 对比度 / 饱和度 / 播放速度 / 音量）能产
生"防重复检测"层面的轻微差异，但操作员和测试用户**肉眼分不出**两个变体
的区别——视觉差异只存在于像素值，没有写在屏幕上。

这次迭代把变体策略从"打乱重排" / "微调滤镜"切换到"在固定叙事上叠加可
插槽内容"，让一份种子视频可以产生很多个**一眼可区分**的变体，适用于真
正的广告 A/B 测试。

### 新增模板字段

四个互相独立、都可选的字段：

- **`intro_card`** —— 开头钩子卡。在种子视频前拼接一段全屏文字卡（默认
  1.5 秒），支持主标题 + 副标题、背景色、字号、字色等。
- **`outro_card`** —— 结尾 CTA 卡，结构同 intro，挂在种子视频后面。
- **`subtitle_bar`** —— 常驻字幕条。在种子视频画面上贴一条 drawbox +
  drawtext 组合，位置可选 top / bottom / center。`bar_color` 设为 `none`
  时只渲文字不带条带。
- **`delivery.safe_area_top` / `safe_area_bottom`** —— 上下安全区。设了
  之后渲染器把源画面缩放到 `(width, height - top - bottom)`，再以偏移
  pad 到完整画布，保证字幕条不压住源画面。启用 `subtitle_bar` 时会
  按条带高度自动预留对应方向的 safe_area。

### 新增 / 调整的渲染路径

- `backend/app/services/ffmpeg.py`
  - 新增 `font_path()`：优先 `FLASHCUTTER_FONT_PATH` 环境变量，fallback
    覆盖 macOS PingFang / STHeiti、Linux Noto CJK / 文泉驿、最后 Helvetica。
  - 新增 `render_card_clip()`：用 `-f lavfi -i color + -f lavfi -i anullsrc`
    生成与输出 dims/fps 匹配的纯色文字 MP4，加 `-r {fps} -fps_mode cfr`
    锁定帧率。
  - `_drawtext_filter` 自动注入 `fontfile=`（这是修一个一直存在的隐性
    bug——之前中文 text_overlays 全部渲不出字符，只显示方框）。
  - `_video_filters` 增加 `safe_area_top` / `safe_area_bottom` 参数，
    采用非居中 pad（`pad=W:H:(W-iw)/2:safe_area_top:black`）。
- `backend/app/api/routes.py`
  - `normalize_template_spec`：把 `subtitle_bar` 转成既有的
    `cover_regions` + `text_overlays`；自动预留 safe_area；把
    `delivery.safe_area_*` 平移到 `layout.safe_area_*`。
  - `build_render_plan_for_task`：把 `intro_card` / `outro_card` /
    `safe_area_*` 写入 plan_json。
  - `render_task_output`：检测到卡片启用 → 预渲两个卡片 mp4 → 前后拼接
    segment 列表 → 强制走 `render_timeline` 转码路径，保证编码一致。
  - 输出 fps 校验容差从 0.25 放宽到 1.5（concat 后 1% 漂移属正常，仍
    能拦截 15 / 30 / 60 这种量级错误）。
- `backend/app/services/storage.py`
  - 新增 `task_card_path(task_id, kind)`，卡片落到 `storage/temp/task-{id}-{intro,outro}.mp4`。

### Schema 扩展

`backend/app/schemas.py`：
- 新 model：`TemplateCardSpec`、`TemplateSubtitleBarSpec`（启用时强制要求
  非空文案）。
- `TemplateDeliverySpec` 增加 `safe_area_top` / `safe_area_bottom`，并校
  验 `safe_area_top + safe_area_bottom < height`。
- `TemplateLayoutSpec` 增加同样两个字段供归一化输出使用。
- `TemplateTextOverlay.x` / `y` 支持 `Union[int, str]`——允许传 ffmpeg
  表达式如 `(w-text_w)/2`，便于字幕条做真正的水平居中。
- `TemplateSpec` 增加 `intro_card` / `subtitle_bar` / `outro_card`。

### 内置 demo 模板

`backend/app/main.py:seed_builtin_template` 新增 `hook_cta_demo`：
9:16 / 1080×1920 / 30fps + 黑底钩子卡 "3 秒看懂" + 底部字幕条 "真实记录
· 30 天亲测" + 红底 CTA 卡 "点击购买"。开箱可用。

### 前端

- `frontend/src/pages/TemplatesPage.tsx`：在模板编辑表单下方追加 4 个
  `<details>` 折叠分区（开头钩子卡 / 字幕条 / 结尾 CTA 卡 / 安全区）。
- `frontend/src/api/templateDisplay.ts`：模板列表摘要追加角标
  `钩子卡 · 字幕条 · CTA 卡`，操作员扫一眼就能看出模板启用了哪几个变体
  维度。
- `frontend/src/styles.css`：新增 `.template-section` / `.form-wide` /
  `.form-hint`。

### 校验与验证

- `backend/tests/` 新增 4 个测试文件，30 个用例覆盖：卡片字段约束、归一化
  转换、subtitle_bar 自动 safe_area、bar_color=none 跳过 drawbox、
  非居中 pad 滤镜字符串、`fontfile=` 环境变量优先级、CJK 文本 escape。
  原有 13 个用例保持全绿。
- 前端 `npm run build` 通过。
- 端到端真实 ffmpeg 渲染：生成种子视频 → 创建 Variant A / B 两个模板 →
  通过 `/api/assets/{id}/render-variants` 批量渲染 → 抓 0.5s / 5s / 11s
  截帧确认中文渲染、卡片 / 字幕条 / 安全区配合无误，两个变体一眼可分辨。

### 顺手修正

- `AGENTS.md` 和 `CODEX_PROJECT_HANDOFF.md` 中过时的工作目录路径
  `/Users/luwei/Documents/Codex/2026-05-09/flashcutter` →
  `/Users/luwei/cc-test/flashcutter`。
- `.env.example` 增加 `FLASHCUTTER_FONT_PATH` 注释说明。
- `.gitignore` 增加 `backend/storage_demo/`、`backend/build/`、
  `backend/*.egg-info/`，避免 build artifacts 入库。

### 已知问题 / 后续讨论项

1. **字幕条会顺带渲到 intro/outro 卡上**。原因：`render_timeline` 把
   滤镜统一应用到所有片段，包括预渲的卡片。视觉上反而像品牌连贯条，
   暂不算 bug；试生产观察后再判断是否需要 `subtitle_bar.apply_to_cards`
   开关。
2. **API 没有强制鉴权**。前端的 phone/password 仍只是本地门禁，FastAPI
   路由没有 auth 中间件。上公网前必须补。
3. **任务队列内存型**。进程重启在飞任务丢失，状态会不一致。
4. **Alembic 迁移**未引入；目前靠 `Base.metadata.create_all` + 手动 ALTER
   兼容。schema 字段持续增长前需要先铺迁移基建。
