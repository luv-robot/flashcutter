import { useState } from 'react';
import { outputFileUrl, productionRunPackageUrl } from '../api/client';
import type { OutputReview } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

type PlatformPackagesPageProps = {
  outputs: OutputReview[];
};

const platforms = ['巨量引擎', '腾讯广告', '阿里广告平台'];

type PackageDraft = {
  platform: string;
  productName: string;
  landingPage: string;
  industry: string;
  materialTitle: string;
  rightsConfirmed: boolean;
};

export function PlatformPackagesPage({ outputs }: PlatformPackagesPageProps) {
  const approvedOutputs = outputs.filter((output) => output.review_status === 'approved');
  const packages = groupApprovedOutputs(approvedOutputs);
  const [drafts, setDrafts] = useState<Record<string, PackageDraft>>({});
  const [mockPushStatus, setMockPushStatus] = useState<Record<string, string>>({});

  function draftFor(key: string): PackageDraft {
    return drafts[key] ?? {
      platform: platforms[0],
      productName: '',
      landingPage: '',
      industry: '',
      materialTitle: '',
      rightsConfirmed: false
    };
  }

  function updateDraft(key: string, patch: Partial<PackageDraft>) {
    setDrafts((current) => ({
      ...current,
      [key]: { ...draftFor(key), ...patch }
    }));
    setMockPushStatus((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  return (
    <section className="platform-package-page">
      <div className="panel package-flow-panel">
        <div>
          <div className="panel-kicker">投放包</div>
          <h2>平台投放包</h2>
          <p>选择过审视频，完成平台规格预检后导出或推送。</p>
        </div>
        <div className="package-steps" aria-label="投放包流程">
          {['选择过审视频', '选择平台', '填写投放信息', '规格预检', '生成投放包', '推送或导出'].map(
            (step, index) => (
              <span key={step} className={index === 0 ? 'current-package-step' : ''}>
                {step}
              </span>
            )
          )}
        </div>
      </div>

      <div className="workspace-grid package-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>平台</h2>
              <p>先生成交付包，API 推送在接口层接入后启用。</p>
            </div>
          </div>
          <div className="platform-list">
            {platforms.map((platform, index) => (
              <button
                key={platform}
                className={index === 0 ? 'selected-output' : ''}
                type="button"
              >
                {platform}
              </button>
            ))}
          </div>
          <p className="rights-note">当前只做交付包和 mock 推送，不绕过平台素材审核。</p>
        </section>

        <section className="panel wide">
          <div className="panel-header">
            <div>
              <h2>过审视频</h2>
              <p>{approvedOutputs.length} 条视频可进入投放包。</p>
            </div>
            <StatusBadge value={approvedOutputs.length > 0 ? 'ready' : 'draft'} />
          </div>
          <div className="package-card-list">
            {packages.length === 0 ? (
              <p className="empty-state">暂无过审视频。</p>
            ) : (
              packages.map((item) => (
                <PackageCard
                  key={item.key}
                  item={item}
                  draft={draftFor(item.key)}
                  mockPushStatus={mockPushStatus[item.key] ?? ''}
                  onDraftChange={(patch) => updateDraft(item.key, patch)}
                  onMockPush={(message) =>
                    setMockPushStatus((current) => ({ ...current, [item.key]: message }))
                  }
                />
              ))
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

function PackageCard({
  item,
  draft,
  mockPushStatus,
  onDraftChange,
  onMockPush
}: {
  item: ApprovedPackageGroup;
  draft: PackageDraft;
  mockPushStatus: string;
  onDraftChange: (patch: Partial<PackageDraft>) => void;
  onMockPush: (message: string) => void;
}) {
  const checks = packageChecks(item, draft);
  const canGenerate = checks.every((check) => check.ok);

  return (
    <article className="package-card">
      <div>
        <strong>{item.title}</strong>
        <span>
          {item.outputs.length} 条过审视频 · {item.assetFilename}
        </span>
      </div>
      <div className="package-form-grid">
        <label>
          平台
          <select value={draft.platform} onChange={(event) => onDraftChange({ platform: event.target.value })}>
            {platforms.map((platform) => (
              <option key={platform} value={platform}>{platform}</option>
            ))}
          </select>
        </label>
        <label>
          商品 / 服务
          <input
            value={draft.productName}
            onChange={(event) => onDraftChange({ productName: event.target.value })}
            placeholder="例如：新品活动套装"
          />
        </label>
        <label>
          落地页
          <input
            value={draft.landingPage}
            onChange={(event) => onDraftChange({ landingPage: event.target.value })}
            placeholder="https://..."
          />
        </label>
        <label>
          行业
          <input
            value={draft.industry}
            onChange={(event) => onDraftChange({ industry: event.target.value })}
            placeholder="例如：食品饮料"
          />
        </label>
        <label>
          素材标题
          <input
            value={draft.materialTitle}
            onChange={(event) => onDraftChange({ materialTitle: event.target.value })}
            placeholder="用于平台素材管理"
          />
        </label>
        <label className="checkbox-row form-checkbox">
          <input
            type="checkbox"
            checked={draft.rightsConfirmed}
            onChange={(event) => onDraftChange({ rightsConfirmed: event.target.checked })}
          />
          <span>
            <strong>确认素材权利已完成</strong>
            <small>只确认交付前检查，不代表平台审核通过。</small>
          </span>
        </label>
      </div>
      <div className="package-preflight-list">
        {checks.map((check) => (
          <div key={check.label} className={check.ok ? 'package-check-ok' : 'package-check-blocked'}>
            <StatusBadge value={check.ok ? 'ready' : 'failed'} />
            <span>{check.label}</span>
          </div>
        ))}
      </div>
      <div className="package-output-list">
        {item.outputs.map((output) => (
          <a key={output.output_id} href={outputFileUrl(output.output_id)} target="_blank" rel="noreferrer">
            #{output.output_id} {output.template_name} · {outputSummary(output.render_plan)}
          </a>
        ))}
      </div>
      <div className="package-status-line">
        <StatusBadge value={canGenerate ? 'ready' : 'draft'} />
        <span>{canGenerate ? '规格预检通过，可生成交付物。' : '还有字段或确认项未完成。'}</span>
      </div>
      {mockPushStatus && <p className="notice">{mockPushStatus}</p>}
      <div className="button-row">
        {item.productionRunId ? (
          <a
            className={`button-link primary-link ${canGenerate ? '' : 'disabled-link'}`}
            href={canGenerate ? productionRunPackageUrl(item.productionRunId) : undefined}
            aria-disabled={!canGenerate}
          >
            生成投放包
          </a>
        ) : (
          <button className="primary-action" type="button" disabled>
            生成投放包
          </button>
        )}
        <button
          className="secondary-action"
          type="button"
          disabled={!canGenerate}
          onClick={() =>
            onMockPush(
              `${draft.platform} mock 推送已完成：${item.outputs.length} 条视频已生成待接入 payload。`
            )
          }
        >
          模拟推送
        </button>
        <button
          className="secondary-action"
          type="button"
          disabled={!canGenerate}
          onClick={() => downloadCsv(item, draft)}
        >
          导出CSV
        </button>
      </div>
    </article>
  );
}

function packageChecks(item: ApprovedPackageGroup, draft: PackageDraft) {
  return [
    { label: '至少 1 条过审视频', ok: item.outputs.length > 0 },
    { label: '已选择平台', ok: Boolean(draft.platform) },
    { label: '商品 / 服务已填写', ok: Boolean(draft.productName.trim()) },
    { label: '落地页为 https 链接', ok: /^https:\/\//i.test(draft.landingPage.trim()) },
    { label: '行业已填写', ok: Boolean(draft.industry.trim()) },
    { label: '素材标题已填写', ok: Boolean(draft.materialTitle.trim()) },
    { label: '素材权利已确认', ok: draft.rightsConfirmed }
  ];
}

function downloadCsv(item: ApprovedPackageGroup, draft: PackageDraft) {
  const rows = [
    ['platform', 'package', 'output_id', 'asset_filename', 'template', 'material_title', 'product', 'industry', 'landing_page', 'video_url'],
    ...item.outputs.map((output) => [
      draft.platform,
      item.title,
      String(output.output_id),
      output.asset_filename,
      output.template_name,
      draft.materialTitle,
      draft.productName,
      draft.industry,
      draft.landingPage,
      outputFileUrl(output.output_id)
    ])
  ];
  const csv = rows.map((row) => row.map(csvCell).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${safeFilename(item.title)}-platform-package.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string) {
  return `"${value.replace(/"/g, '""')}"`;
}

function safeFilename(value: string) {
  return value.trim().replace(/[^a-z0-9\u4e00-\u9fa5]+/gi, '-').replace(/^-+|-+$/g, '') || 'package';
}

function outputSummary(plan: Record<string, unknown>) {
  const output = record(plan.output);
  const layout = record(plan.layout);
  const width = typeof output.width === 'number' ? output.width : null;
  const height = typeof output.height === 'number' ? output.height : null;
  const fps = typeof output.fps === 'number' ? output.fps : null;
  const fit = typeof layout.fit === 'string' ? layout.fit : 'original';
  return [width && height ? `${width}x${height}` : 'source', fps ? `${fps}fps` : null, fit]
    .filter(Boolean)
    .join(' · ');
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

type ApprovedPackageGroup = {
  key: string;
  title: string;
  assetFilename: string;
  productionRunId: number | null;
  outputs: OutputReview[];
};

function groupApprovedOutputs(outputs: OutputReview[]): ApprovedPackageGroup[] {
  const map = new Map<string, ApprovedPackageGroup>();
  outputs.forEach((output) => {
    const key = output.production_run_id
      ? `run-${output.production_run_id}`
      : `asset-${output.asset_id}`;
    const current =
      map.get(key) ??
      {
        key,
        title: output.production_run_name || output.asset_filename,
        assetFilename: output.asset_filename,
        productionRunId: output.production_run_id,
        outputs: []
      };
    current.outputs.push(output);
    map.set(key, current);
  });
  return Array.from(map.values());
}
