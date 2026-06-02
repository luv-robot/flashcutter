export const videoClipTypes = [
  { value: 'hook', label: 'Hook' },
  { value: 'cta', label: 'CTA' },
  { value: 'broll', label: 'B-roll' },
  { value: 'reaction', label: 'Reaction' },
  { value: 'meme', label: 'Meme' },
  { value: 'product_motion', label: 'Product motion' },
  { value: 'intro', label: '前贴片' },
  { value: 'outro', label: '后贴片' }
];

export const imageAssetTypes = [
  { value: 'frame', label: '图片框' },
  { value: 'logo', label: 'Logo' },
  { value: 'cover', label: '贴片封面' },
  { value: 'poster', label: '海报图' },
  { value: 'reference', label: '参考图' }
];

export const rightsStatusOptions = [
  { value: 'licensed', label: '已授权' },
  { value: 'needs_review', label: '待确认' },
  { value: 'reference_only', label: '仅参考' }
];

export function labelForAIAssetType(value: string): string {
  return (
    [...videoClipTypes, ...imageAssetTypes].find((item) => item.value === value)?.label ??
    value
  );
}

export function labelForRightsStatus(value: string): string {
  return rightsStatusOptions.find((item) => item.value === value)?.label ?? value;
}

export function rightsTag(value: string): string {
  return `rights-${value}`;
}

export function rightsStatusFromTags(tags: Array<{ tag: string }>): string {
  const tag = tags.find((item) => item.tag.startsWith('rights-'));
  return tag ? tag.tag.replace(/^rights-/, '') : '';
}

export function formatAssetSize(value: number | null): string {
  if (!value) return '0 KB';
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
