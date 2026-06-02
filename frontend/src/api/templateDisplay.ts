import type { Template } from './types';

type AnyRecord = Record<string, unknown>;

export function templateTitle(template: Template): string {
  const goal = creativeGoal(template);
  const title = text(goal.title);
  return title || text(template.json_spec.name) || readableName(template.name);
}

export function templateSummary(template: Template): string {
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
