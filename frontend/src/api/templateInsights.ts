import { templatePlanCategory, templateRequiredFieldLabels } from './templateDisplay';
import type { Asset, OutputReview, Template } from './types';

export type TemplateRecommendationLevel = 'recommended' | 'try' | 'caution';

export type TemplateRecommendation = {
  level: TemplateRecommendationLevel;
  score: number;
  reasons: string[];
  cautions: string[];
};

export type AssetHealth = {
  status: 'ready' | 'warning' | 'blocked';
  summary: string;
  facts: string[];
  cautions: string[];
};

export type TemplateUsageStats = {
  generatedCount: number;
  approvedCount: number;
  needsChangesCount: number;
  rejectedCount: number;
  discardedCount: number;
  passRate: number | null;
  topFeedbackReasons: string[];
};

export type ReviewNextRoundAdvice = {
  totalFeedbackCount: number;
  topReasons: string[];
  recommendations: string[];
};

export function assetHealth(asset: Asset | undefined, outputPresetId: string): AssetHealth {
  if (!asset) {
    return {
      status: 'blocked',
      summary: '还未选择种子视频',
      facts: ['先选择一条已授权视频，再推荐方案包。'],
      cautions: ['未选择视频时只能按通用方案判断。']
    };
  }
  const facts = [
    `素材 #${asset.id}`,
    asset.status === 'ready' ? '状态可用' : `状态：${asset.status}`,
    asset.duration_seconds ? `时长 ${asset.duration_seconds.toFixed(1)}s` : '',
    asset.width && asset.height ? `${asset.width}x${asset.height}` : '',
    outputPresetLabel(outputPresetId)
  ].filter(Boolean);
  const cautions = [
    asset.status !== 'ready' ? '素材状态不是 ready，可能无法入队。' : '',
    asset.duration_seconds && asset.duration_seconds < 6 ? '视频时长偏短，强开场和片段重组空间有限。' : '',
    asset.duration_seconds && asset.duration_seconds > 60 ? '视频时长偏长，建议先小批量预检。' : '',
    isLandscape(asset) && outputPresetId.includes('9_16') ? '横版素材做竖版填满时要重点检查主体裁切。' : '',
    isPortrait(asset) && outputPresetId.includes('16_9') ? '竖版素材做横版时可能出现大面积留边或裁切。' : ''
  ].filter(Boolean);
  return {
    status: asset.status !== 'ready' ? 'blocked' : cautions.length ? 'warning' : 'ready',
    summary: asset.status === 'ready' ? '素材可进入推荐' : '素材状态需要先处理',
    facts,
    cautions
  };
}

export function templateRecommendation(
  template: Template,
  asset: Asset | undefined,
  outputPresetId: string
): TemplateRecommendation {
  const category = templatePlanCategory(template);
  const requiredFields = templateRequiredFieldLabels(template);
  const reasons: string[] = [];
  const cautions: string[] = [];
  let score = 48;

  if (!asset) {
    cautions.push('未选择视频，暂按通用素材判断。');
  } else if (asset.status === 'ready') {
    score += 18;
    reasons.push('种子视频状态可用。');
  } else {
    score -= 30;
    cautions.push('素材状态不是 ready。');
  }

  if (requiredFields.length === 0) {
    score += 16;
    reasons.push('无需额外素材字段，适合快速试跑。');
  } else {
    score -= Math.min(18, requiredFields.length * 6);
    cautions.push(`需要先准备：${requiredFields.join('、')}。`);
  }

  if (/Hook|基础安全|CTA/.test(category)) {
    score += 12;
    reasons.push(`${category}适合第一轮扩量。`);
  } else if (/产品|证据/.test(category)) {
    score += 6;
    reasons.push(`${category}适合已有明确产品露出的素材。`);
  }

  if (asset?.duration_seconds) {
    if (asset.duration_seconds >= 8 && asset.duration_seconds <= 45) {
      score += 10;
      reasons.push('时长适合短视频扩量。');
    } else if (asset.duration_seconds < 6) {
      score -= 12;
      cautions.push('原片过短，建议先少量测试。');
    } else if (asset.duration_seconds > 60) {
      score -= 8;
      cautions.push('原片较长，预检后再批量入队。');
    }
  }

  if (asset && isLandscape(asset) && outputPresetId === 'vertical_9_16_cover') {
    score -= 10;
    cautions.push('横版转竖版填满有裁切风险。');
  }
  if (asset && isPortrait(asset) && outputPresetId === 'horizontal_16_9_cover') {
    score -= 10;
    cautions.push('竖版转横版有裁切或留边风险。');
  }

  if (score >= 72 && cautions.length <= 1) {
    return { level: 'recommended', score, reasons: reasons.slice(0, 3), cautions: cautions.slice(0, 2) };
  }
  if (score >= 52) {
    return { level: 'try', score, reasons: reasons.slice(0, 3), cautions: cautions.slice(0, 2) };
  }
  return { level: 'caution', score, reasons: reasons.slice(0, 3), cautions: cautions.slice(0, 3) };
}

export function templateUsageStats(template: Template, outputs: OutputReview[]): TemplateUsageStats {
  const matched = outputs.filter((output) => output.template_id === template.id);
  const approvedCount = matched.filter((output) => output.review_status === 'approved').length;
  const needsChangesCount = matched.filter((output) => output.review_status === 'needs_changes').length;
  const rejectedCount = matched.filter((output) => output.review_status === 'rejected').length;
  const discardedCount = matched.filter((output) => output.review_status === 'discarded').length;
  return {
    generatedCount: matched.length,
    approvedCount,
    needsChangesCount,
    rejectedCount,
    discardedCount,
    passRate: matched.length ? approvedCount / matched.length : null,
    topFeedbackReasons: topFeedbackReasons(matched)
  };
}

export function reviewNextRoundAdvice(outputs: OutputReview[]): ReviewNextRoundAdvice {
  const reasons = topFeedbackReasons(outputs, 3);
  const allRequests = outputs.flatMap(changeRequestsForOutput);
  const recommendations = new Set<string>();
  allRequests.forEach((request) => {
    const text = `${request.category} ${request.target} ${request.request}`;
    if (/开场|hook|前三秒|钩子/i.test(text)) {
      recommendations.add('下一轮优先使用「Hook 扩量 / 强开场」方案，并准备 5-10 条不同开场文字。');
    }
    if (/产品|露出|太晚|步骤|特写/i.test(text)) {
      recommendations.add('下一轮尝试「产品证据强化」，把产品露出和关键动作提前。');
    }
    if (/cta|收口|行动|下载|领取/i.test(text)) {
      recommendations.add('下一轮叠加「CTA 强化」，把结尾行动提示做成独立变体。');
    }
    if (/裁切|遮挡|主体|边缘/i.test(text)) {
      recommendations.add('下一轮改用更保守的输出规格或 contain 适配，并重点检查主体位置。');
    }
    if (/配乐|音乐|原声/i.test(text)) {
      recommendations.add('下一轮拆分配乐方案：保留原声版和替换配乐版分别测试。');
    }
    if (/变化太小|差异|疲劳/i.test(text)) {
      recommendations.add('下一轮提高激进程度，增加字幕、开头片段或节奏差异。');
    }
    if (/太像硬广|原生|包装感/i.test(text)) {
      recommendations.add('下一轮降低包装感，保留更多真人实拍原生质感。');
    }
  });
  if (recommendations.size === 0 && allRequests.length > 0) {
    recommendations.add('下一轮先按结构化原因小批量再生产，再根据通过率扩大数量。');
  }
  return {
    totalFeedbackCount: allRequests.length,
    topReasons: reasons,
    recommendations: Array.from(recommendations).slice(0, 4)
  };
}

function topFeedbackReasons(outputs: OutputReview[], limit = 3): string[] {
  const counts = new Map<string, number>();
  outputs.flatMap(changeRequestsForOutput).forEach((request) => {
    const key = feedbackReasonLabel(request);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, limit)
    .map(([label, count]) => `${label} ${count} 次`);
}

function changeRequestsForOutput(output: OutputReview): Array<{
  category: string;
  target: string;
  request: string;
}> {
  const feedback = output.review_feedback ?? {};
  const requests = feedback.change_requests;
  if (!Array.isArray(requests)) return [];
  return requests
    .filter((item): item is Record<string, unknown> =>
      Boolean(item) && typeof item === 'object' && !Array.isArray(item)
    )
    .map((item) => ({
      category: typeof item.category === 'string' ? item.category : 'other',
      target: typeof item.target === 'string' ? item.target : '',
      request: typeof item.request === 'string' ? item.request : ''
    }))
    .filter((item) => item.request || item.target);
}

function feedbackReasonLabel(request: { category: string; target: string; request: string }) {
  const text = `${request.target} ${request.request}`;
  if (/开场|hook|前三秒|钩子/i.test(text)) return '开场弱';
  if (/产品|露出|太晚|步骤|特写/i.test(text)) return '产品太晚';
  if (/字幕|可读|字号/i.test(text)) return '字幕难读';
  if (/配乐|音乐|原声/i.test(text)) return '配乐不合适';
  if (/节奏|慢|停顿/i.test(text)) return '节奏太慢';
  if (/裁切|遮挡|主体/i.test(text)) return '裁切挡主体';
  if (/cta|收口|行动/i.test(text)) return 'CTA 不明显';
  if (/变化太小|差异/i.test(text)) return '变化太小';
  if (/不像广告/i.test(text)) return '不像广告';
  if (/太像硬广|包装感/i.test(text)) return '太像广告';
  if (/权利|事实|授权|合规/i.test(text)) return '事实/授权风险';
  return request.target || request.category || '其他反馈';
}

function outputPresetLabel(value: string) {
  const labels: Record<string, string> = {
    vertical_9_16_cover: '输出：竖版填满',
    vertical_9_16_contain: '输出：竖版保留完整',
    square_1_1_contain: '输出：方版',
    horizontal_16_9_cover: '输出：横版',
    source_original: '输出：保持原尺寸'
  };
  return labels[value] ?? `输出：${value}`;
}

function isLandscape(asset: Asset) {
  return Boolean(asset.width && asset.height && asset.width > asset.height);
}

function isPortrait(asset: Asset) {
  return Boolean(asset.width && asset.height && asset.height > asset.width);
}
