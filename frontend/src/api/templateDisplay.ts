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

function readableName(value: string): string {
  return value
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
