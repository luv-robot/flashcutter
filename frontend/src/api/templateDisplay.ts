import type { Template } from './types';

type AnyRecord = Record<string, unknown>;

export function templateTitle(template: Template): string {
  const goal = creativeGoal(template);
  const title = text(goal.title);
  return title || text(template.json_spec.name) || readableName(template.name);
}

export function templateSummary(template: Template): string {
  if (template.json_spec.schema_version === 3) {
    return v3TemplateSummary(template);
  }
  const goal = creativeGoal(template);
  const editing = record(record(template.json_spec.blueprint).editing);
  const delivery = record(record(template.json_spec.render_preset).delivery);

  const parts = [
    text(goal.audience),
    text(goal.tone),
    durationSummary(editing),
    clipSummary(editing),
    deliverySummary(delivery),
    recipeModuleSummary(template)
  ].filter(Boolean);

  return parts.join(' · ') || `模板 #${template.id}`;
}

export function templateBadge(template: Template): string {
  return template.is_builtin ? '内置' : `v${template.version}`;
}

export function templatePlanCategory(template: Template): string {
  const spec = template.json_spec;
  if (spec.schema_version === 3) {
    const labels: Record<string, string> = {
      hook_expansion: 'Hook 扩量',
      packaging: '品牌包装',
      brand_packaging: '统一品牌',
      platform_dedup: '平台去重',
      cta_expansion: 'CTA 强化'
    };
    const category = text(spec.category);
    return labels[category] ?? (category || '方案包');
  }
  const goal = creativeGoal(template);
  const title = text(goal.title);
  if (/testimonial|proof|证据|证明/i.test(`${template.name} ${title}`)) return '证据强化';
  if (/unboxing|steps|步骤|开箱/i.test(`${template.name} ${title}`)) return '产品步骤';
  if (/hook|开场/i.test(`${template.name} ${title}`)) return 'Hook 扩量';
  return '基础安全扩量';
}

export function templateExpectedOutcome(template: Template): string {
  const spec = template.json_spec;
  if (spec.schema_version === 3) {
    const operations = Array.isArray(spec.operations) ? spec.operations : [];
    const labels = operations
      .map((operation) => {
        const item = record(operation);
        return text(item.label) || v3OperationLabel(text(item.type));
      })
      .filter(Boolean);
    return labels.length > 0
      ? labels.slice(0, 4).join(' + ')
      : '按方案包规则生成可审核变体';
  }

  const blueprint = record(spec.blueprint);
  const editing = record(blueprint.editing);
  const stylePack = record(spec.style_pack);
  const transformations = record(stylePack.transformations);
  const pieces = [
    text(editing.cut_style) ? '重组片段' : '',
    text(transformations.visual_style) ? visualStyleLabel(text(transformations.visual_style)) : '',
    text(transformations.transition_style) ? transitionLabel(text(transformations.transition_style)) : '',
    numberValue(transformations.playback_speed)
      ? `${numberValue(transformations.playback_speed)}x 节奏`
      : '',
    record(spec.copy_pack).name ? '叠字变体' : ''
  ].filter(Boolean);
  return pieces.join(' + ') || '生成一组低成本广告变体';
}

export function templateSuitableFor(template: Template): string[] {
  const spec = template.json_spec;
  if (spec.schema_version === 3) {
    const requirements = record(spec.input_requirements);
    const ratios = Array.isArray(requirements.accepted_seed_ratios)
      ? requirements.accepted_seed_ratios.filter((item): item is string => typeof item === 'string')
      : [];
    const category = text(spec.category);
    const items = [
      text(spec.use_case),
      numberValue(requirements.min_seed_duration_seconds)
        ? `时长不少于 ${numberValue(requirements.min_seed_duration_seconds)} 秒的已授权视频`
        : '已授权视频素材',
      ratios.length > 0 ? `支持 ${ratios.join(' / ')} 素材比例` : ''
    ].filter(Boolean);
    if (category === 'hook_expansion') {
      items.push('需要快速测试多种前三秒开场文案');
    }
    return uniqueNonEmpty(items).slice(0, 4);
  }

  const blueprint = record(spec.blueprint);
  const contract = record(blueprint.production_contract);
  const goal = record(blueprint.creative_goal);
  return uniqueNonEmpty([
    text(contract.use_case),
    text(goal.audience) ? `面向${text(goal.audience)}` : '',
    '已确认授权的真人实拍广告素材',
    durationSuitableText(spec)
  ]).slice(0, 4);
}

export function templateNotSuitableFor(template: Template): string[] {
  const spec = template.json_spec;
  if (spec.schema_version === 3) {
    const category = text(spec.category);
    const fields = runtimeFields(template);
    const requiredAssets = fields.filter((field) => field.required && field.fieldType === 'asset');
    const items = [
      category === 'hook_expansion' ? '原片前三秒已经有密集字幕或强口播钩子' : '',
      category === 'hook_expansion' ? '画面主体贴近顶部，新增开场字可能遮挡主体' : '',
      requiredAssets.length > 0
        ? `缺少${requiredAssets.map((field) => field.label).join('、')}`
        : '',
      '素材授权或品牌合规尚未确认'
    ];
    return uniqueNonEmpty(items).slice(0, 4);
  }

  const delivery = record(record(spec.render_preset).delivery);
  const transformations = record(record(spec.style_pack).transformations);
  const fit = text(delivery.fit);
  const items = [
    fit === 'cover' ? '主体靠近画面边缘，裁切风险高' : '',
    record(spec.music).track_id || record(spec.music).mode === 'replace'
      ? '强依赖原声口播且不能替换配乐'
      : '',
    text(transformations.transition_style) && text(transformations.transition_style) !== 'hard_cut'
      ? '品牌规范不允许明显转场特效'
      : '',
    '素材授权或事实表述无法确认'
  ];
  return uniqueNonEmpty(items).slice(0, 4);
}

export function templateRequiredFieldLabels(template: Template): string[] {
  return runtimeFields(template)
    .filter((field) => field.required)
    .map((field) => field.label);
}

function durationSummary(editing: AnyRecord): string {
  const duration = numberValue(editing.target_duration_seconds);
  return duration ? `目标 ${duration} 秒` : '';
}

function clipSummary(editing: AnyRecord): string {
  const count = numberValue(editing.max_clip_count);
  const clipDuration = numberValue(editing.clip_duration_seconds);
  const pieces = [];
  if (count) pieces.push(`${count} 段`);
  if (clipDuration) pieces.push(`每段 ${clipDuration} 秒`);
  return pieces.join(', ');
}

function deliverySummary(delivery: AnyRecord): string {
  const aspect = text(delivery.aspect_ratio);
  const width = numberValue(delivery.width);
  const height = numberValue(delivery.height);
  if (aspect && aspect !== 'source') return aspect;
  if (width && height) return `${width}x${height}`;
  return '';
}

function creativeGoal(template: Template): AnyRecord {
  return record(record(template.json_spec.blueprint).creative_goal);
}

function recipeModuleSummary(template: Template): string {
  const preset = record(template.json_spec.render_preset);
  const style = record(template.json_spec.style_pack);
  return [text(preset.name), text(style.name)].filter(Boolean).join(' / ');
}

function v3TemplateSummary(template: Template): string {
  const operations = Array.isArray(template.json_spec.operations)
    ? template.json_spec.operations
    : [];
  const labels = operations.map((operation) => {
    const item = record(operation);
    return text(item.label) || v3OperationLabel(text(item.type));
  }).filter(Boolean);
  const preset = text(template.json_spec.output_preset_id);
  return [
    text(template.json_spec.category),
    labels.slice(0, 3).join(' / '),
    preset
  ].filter(Boolean).join(' · ') || `方案包 #${template.id}`;
}

function v3OperationLabel(value: string): string {
  const labels: Record<string, string> = {
    resize_canvas: '输出规格',
    text_placeholder: '本次文案',
    cover_region: '安全区',
    replace_music: '替换配乐',
    prepend_clip: '前贴片',
    append_clip: '后贴片',
    overlay_logo: 'Logo',
    overlay_frame: '图片框'
  };
  return labels[value] ?? value;
}

function record(value: unknown): AnyRecord {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as AnyRecord)
    : {};
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' ? value : null;
}

type RuntimeFieldDisplay = {
  label: string;
  required: boolean;
  fieldType: string;
};

function runtimeFields(template: Template): RuntimeFieldDisplay[] {
  const fields = template.json_spec.runtime_fields;
  if (!Array.isArray(fields)) return [];
  return fields
    .filter((field): field is AnyRecord => Boolean(field) && typeof field === 'object')
    .map((field) => ({
      label: text(field.label) || text(field.key) || '本次字段',
      required: field.required === true,
      fieldType: text(field.field_type)
    }));
}

function durationSuitableText(spec: AnyRecord): string {
  const editing = record(record(spec.blueprint).editing);
  const duration = numberValue(editing.target_duration_seconds);
  return duration ? `适合约 ${duration} 秒左右的短视频试生产` : '';
}

function visualStyleLabel(value: string): string {
  const labels: Record<string, string> = {
    natural: '自然原片',
    clean_ad: '清爽广告',
    warm_lifestyle: '暖调生活方式',
    cool_tech: '冷调科技感',
    punchy_social: '高冲击社媒感',
    soft_beauty: '柔和美颜感'
  };
  return labels[value] ?? value;
}

function transitionLabel(value: string): string {
  const labels: Record<string, string> = {
    hard_cut: '硬切',
    flash_white: '闪白',
    flash_black: '闪黑',
    soft_fade: '轻淡入'
  };
  return labels[value] ?? value;
}

function uniqueNonEmpty(values: string[]): string[] {
  const seen = new Set<string>();
  return values
    .map((value) => value.trim())
    .filter(Boolean)
    .filter((value) => {
      if (seen.has(value)) return false;
      seen.add(value);
      return true;
    });
}

function readableName(value: string): string {
  return value
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
