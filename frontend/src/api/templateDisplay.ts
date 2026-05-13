import type { Template } from './types';

type AnyRecord = Record<string, unknown>;

export function templateTitle(template: Template): string {
  const goal = record(template.json_spec.creative_goal);
  const title = text(goal.title);
  return title || readableName(template.name);
}

export function templateSummary(template: Template): string {
  const goal = record(template.json_spec.creative_goal);
  const editing = record(template.json_spec.editing);
  const delivery = record(template.json_spec.delivery);
  const legacySelection = record(template.json_spec.selection);
  const legacySegments = record(template.json_spec.segments);

  const parts = [
    text(goal.audience),
    text(goal.tone),
    durationSummary(editing, legacySelection),
    clipSummary(editing, legacySegments),
    deliverySummary(delivery),
    variantFeatureSummary(template)
  ].filter(Boolean);

  return parts.join(' · ') || `模板 #${template.id}`;
}

function variantFeatureSummary(template: Template): string {
  const intro = record(template.json_spec.intro_card);
  const bar = record(template.json_spec.subtitle_bar);
  const outro = record(template.json_spec.outro_card);
  const badges = [];
  if (intro.enabled) badges.push('钩子卡');
  if (bar.enabled) badges.push('字幕条');
  if (outro.enabled) badges.push('CTA 卡');
  return badges.join(' + ');
}

export function templateBadge(template: Template): string {
  return template.is_builtin ? '内置' : `v${template.version}`;
}

function durationSummary(editing: AnyRecord, selection: AnyRecord): string {
  const duration = numberValue(editing.target_duration_seconds)
    ?? numberValue(selection.max_total_duration);
  return duration ? `目标 ${duration} 秒` : '';
}

function clipSummary(editing: AnyRecord, segments: AnyRecord): string {
  const count = numberValue(editing.max_clip_count);
  const clipDuration = numberValue(editing.clip_duration_seconds)
    ?? numberValue(segments.segment_seconds);
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
