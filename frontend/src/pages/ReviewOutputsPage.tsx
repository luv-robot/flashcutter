import { useEffect, useMemo, useState } from 'react';
import { api, assetFileUrl, outputFileUrl, productionRunPackageUrl } from '../api/client';
import type { Asset, OutputReview } from '../api/types';
import { JsonBlock } from '../components/JsonBlock';
import { StatusBadge } from '../components/StatusBadge';

type ReviewOutputsPageProps = {
  outputs: OutputReview[];
  assets: Asset[];
  focusedAssetId: number | null;
  onRefresh: () => Promise<void>;
  onOpenPackages: () => void;
};

type ReviewGroup = {
  key: string;
  title: string;
  assetId: number;
  assetFilename: string;
  status: string | null;
  latestCreatedAt: string;
  outputs: OutputReview[];
};

type ChangeRequestDraft = {
  id: string;
  category: string;
  target: string;
  request: string;
  priority: string;
};

const reviewActions = [
  { status: 'approved', label: '通过', helper: '保留该成片用于投放测试。' },
  { status: 'needs_changes', label: '要求修改', helper: '记录反馈，用于生成下一版变体。' },
  { status: 'discarded', label: '丢弃', helper: '从可用成片集合中移除。' },
  { status: 'rejected', label: '拒绝', helper: '标记为已审核但不可用。' }
];

const changeCategories = [
  { value: 'copy', label: '文案' },
  { value: 'crop', label: '裁切' },
  { value: 'pacing', label: '节奏' },
  { value: 'music', label: '配乐' },
  { value: 'template', label: '模板' },
  { value: 'asset_selection', label: '素材选择' },
  { value: 'other', label: '其他' }
];

const feedbackReasonPresets: Array<Omit<ChangeRequestDraft, 'id'>> = [
  {
    category: 'copy',
    target: '开场文字',
    request: '开场钩子不够直接，下一版强化前三秒利益点或结果前置。',
    priority: 'high'
  },
  {
    category: 'asset_selection',
    target: '产品镜头',
    request: '产品出现太晚，下一版把产品露出或关键动作提前。',
    priority: 'high'
  },
  {
    category: 'copy',
    target: '字幕',
    request: '字幕不够易读，下一版放大字号、减少字数或调整背景遮罩。',
    priority: 'medium'
  },
  {
    category: 'music',
    target: '配乐',
    request: '配乐和画面氛围不匹配，下一版更换为更贴近素材节奏的配乐。',
    priority: 'medium'
  },
  {
    category: 'pacing',
    target: '剪辑节奏',
    request: '节奏偏慢，下一版压缩开头停顿并提高前半段信息密度。',
    priority: 'medium'
  },
  {
    category: 'crop',
    target: '画面裁切',
    request: '裁切挡住主体或产品，下一版改用更保守的画面适配。',
    priority: 'high'
  },
  {
    category: 'copy',
    target: 'CTA',
    request: '收口行动提示不明显，下一版强化结尾 CTA。',
    priority: 'medium'
  },
  {
    category: 'template',
    target: '变体差异',
    request: '画面变化太小，下一版提高开头、字幕或节奏变化幅度。',
    priority: 'medium'
  },
  {
    category: 'template',
    target: '广告感',
    request: '不像广告素材，下一版增强产品卖点和转化收口。',
    priority: 'medium'
  },
  {
    category: 'template',
    target: '广告感',
    request: '太像硬广，下一版降低包装感，保留更多原生实拍质感。',
    priority: 'medium'
  },
  {
    category: 'other',
    target: '事实与权利',
    request: '存在事实表述或素材授权风险，下一版先复核文案和素材来源。',
    priority: 'high'
  }
];

export function ReviewOutputsPage({
  outputs,
  assets,
  focusedAssetId,
  onRefresh,
  onOpenPackages
}: ReviewOutputsPageProps) {
  const [assetFilter, setAssetFilter] = useState<number | 'all'>(focusedAssetId ?? 'all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedGroupKey, setSelectedGroupKey] = useState<string | null>(null);
  const [selected, setSelected] = useState<OutputReview | null>(null);
  const [notes, setNotes] = useState('');
  const [reviewerName, setReviewerName] = useState('');
  const [changeRequests, setChangeRequests] = useState<ChangeRequestDraft[]>([]);
  const [priority, setPriority] = useState('');
  const [tags, setTags] = useState('');
  const [showRenderPlan, setShowRenderPlan] = useState(false);
  const [busy, setBusy] = useState(false);

  const reviewGroups = useMemo(() => {
    const visibleOutputs = outputs.filter((output) => {
      const assetMatches = assetFilter === 'all' || output.asset_id === assetFilter;
      const statusMatches = statusFilter === 'all' || output.review_status === statusFilter;
      return assetMatches && statusMatches;
    });
    return groupOutputs(visibleOutputs);
  }, [assetFilter, outputs, statusFilter]);

  const selectedGroup =
    reviewGroups.find((group) => group.key === selectedGroupKey) ?? reviewGroups[0] ?? null;
  const nextPendingOutput = nextReviewableOutput(selectedGroup?.outputs ?? [], selected);
  const selectedGroupStats = selectedGroup ? reviewGroupStats(selectedGroup.outputs) : null;

  useEffect(() => {
    if (focusedAssetId) {
      setAssetFilter(focusedAssetId);
    }
  }, [focusedAssetId]);

  useEffect(() => {
    if (!selectedGroup) {
      setSelectedGroupKey(null);
      setSelected(null);
      hydrateFeedback(null);
      setNotes('');
      return;
    }

    setSelectedGroupKey(selectedGroup.key);
    const nextSelected =
      selectedGroup.outputs.find((output) => output.output_id === selected?.output_id) ??
      selectedGroup.outputs[0] ??
      null;
    setSelected(nextSelected);
    setNotes(nextSelected?.review_notes ?? '');
    hydrateFeedback(nextSelected);
    setShowRenderPlan(false);
  }, [selectedGroup?.key, selectedGroup?.outputs, selected?.output_id]);

  function selectGroup(group: ReviewGroup) {
    setSelectedGroupKey(group.key);
    const nextSelected = group.outputs[0] ?? null;
    selectOutput(nextSelected);
  }

  function selectOutput(output: OutputReview | null) {
    setSelected(output);
    setNotes(output?.review_notes ?? '');
    hydrateFeedback(output);
    setShowRenderPlan(false);
  }

  function hydrateFeedback(output: OutputReview | null) {
    const feedback = output?.review_feedback ?? {};
    const structuredRequests = Array.isArray(feedback.change_requests)
      ? feedback.change_requests.filter(
          (item): item is Record<string, unknown> =>
            item !== null && typeof item === 'object' && !Array.isArray(item)
        )
      : [];
    setReviewerName(String(feedback.reviewer_name ?? ''));
    setChangeRequests(
      structuredRequests.length > 0
        ? structuredRequests.map((request, index) => ({
            id: `saved-${output?.output_id ?? 'output'}-${index}`,
            category: String(request.category ?? 'other'),
            target: String(request.target ?? ''),
            request: String(request.request ?? ''),
            priority: String(request.priority ?? '')
          }))
        : feedback.change_request
          ? [
              {
                id: `legacy-${output?.output_id ?? 'output'}`,
                category: 'other',
                target: '',
                request: String(feedback.change_request),
                priority: String(feedback.priority ?? '')
              }
            ]
          : []
    );
    setPriority(String(feedback.priority ?? ''));
    setTags(Array.isArray(feedback.tags) ? feedback.tags.join(', ') : '');
  }

  async function updateReview(reviewStatus: string) {
    if (!selected) return;
    setBusy(true);
    try {
      const normalizedRequests = normalizedChangeRequests(changeRequests);
      const updated = await api.updateOutputReview(selected.output_id, {
        review_status: reviewStatus,
        review_notes: notes,
        reviewer_name: reviewerName || undefined,
        change_request: normalizedRequests[0]?.request,
        change_requests: normalizedRequests,
        priority: priority || undefined,
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean)
      });
      if (reviewStatus !== 'pending_review') {
        const nextOutput = nextReviewableOutput(selectedGroup?.outputs ?? [], selected);
        if (nextOutput) {
          selectOutput(nextOutput);
        } else {
          setSelected(updated);
        }
      } else {
        setSelected(updated);
      }
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  function addPresetChangeRequest(preset: Omit<ChangeRequestDraft, 'id'>) {
    setChangeRequests((current) => [
      ...current,
      {
        ...preset,
        id: `preset-${Date.now()}-${current.length}`
      }
    ]);
    if (!priority && preset.priority) {
      setPriority(preset.priority);
    }
  }

  function addBlankChangeRequest() {
    setChangeRequests((current) => [
      ...current,
      {
        id: `blank-${Date.now()}-${current.length}`,
        category: 'other',
        target: '',
        request: '',
        priority: priority || ''
      }
    ]);
  }

  function updateChangeRequest(index: number, patch: Partial<ChangeRequestDraft>) {
    setChangeRequests((current) =>
      current.map((request, itemIndex) =>
        itemIndex === index ? { ...request, ...patch } : request
      )
    );
  }

  function removeChangeRequest(index: number) {
    setChangeRequests((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  async function markGroupNeedsRevision() {
    if (!selectedGroup?.outputs[0]?.production_run_id) return;
    setBusy(true);
    try {
      await api.updateProductionRunStatus(
        selectedGroup.outputs[0].production_run_id,
        'needs_revision'
      );
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function downloadApprovedPackage() {
    const productionRunId = selectedGroup?.outputs[0]?.production_run_id;
    if (!productionRunId) return;
    setBusy(true);
    try {
      const estimate = await api.estimateProductionRunPackage(productionRunId);
      const warningLines = [
        `将打包 1 个种子视频和 ${estimate.approved_output_count} 个过审视频。`,
        `预计原始文件容量：${formatBytes(estimate.total_size_bytes)}。`,
        estimate.missing_files.length > 0
          ? `有 ${estimate.missing_files.length} 个文件缺失，将无法完整打包。`
          : ''
      ].filter(Boolean);
      if (estimate.approved_output_count === 0) {
        window.alert('当前批次还没有过审视频，暂时不能打包下载。');
        return;
      }
      if (window.confirm(`${warningLines.join('\n')}\n\n确认开始下载 zip 吗？`)) {
        window.location.href = productionRunPackageUrl(productionRunId);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="review-layout">
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">审核工作台</div>
            <h2>素材批次</h2>
          </div>
          <button className="secondary-action" onClick={onRefresh}>刷新</button>
        </div>
        <label>
          素材筛选
          <select
            value={assetFilter}
            onChange={(event) =>
              setAssetFilter(event.target.value === 'all' ? 'all' : Number(event.target.value))
            }
          >
            <option value="all">全部素材</option>
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                #{asset.id} {asset.original_filename}
              </option>
            ))}
          </select>
        </label>
        <label>
          审核状态
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">全部状态</option>
            <option value="pending_review">待审核</option>
            <option value="approved">已通过</option>
            <option value="needs_changes">需修改</option>
            <option value="rejected">已拒绝</option>
            <option value="discarded">已丢弃</option>
          </select>
        </label>
        <div className="review-group-list">
          {reviewGroups.map((group) => (
            <button
              key={group.key}
              className={`review-group-row ${
                selectedGroup?.key === group.key ? 'selected-output' : ''
              }`}
              onClick={() => selectGroup(group)}
            >
              <span>{group.title}</span>
              <small>
                {group.assetFilename} · {group.outputs.length} 个变体 · {formatDateTime(group.latestCreatedAt)}
              </small>
              <span className="group-status-line">
                <StatusBadge value={group.status ?? dominantReviewStatus(group.outputs)} />
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="panel wide review-stage">
        {selected && selectedGroup ? (
          <>
            <div className="review-stage-header">
              <div>
                <div className="panel-kicker">当前批次</div>
                <h2>{selectedGroup.title}</h2>
                <p>
                  原素材：{selected.asset_filename} · R{selected.revision_number} · 当前变体：
                  {templateLabel(selected)}
                </p>
                {selectedGroupStats && (
                  <div className="review-batch-stats" aria-label="批次审核统计">
                    <span>{selectedGroupStats.approved} 已通过</span>
                    <span>{selectedGroupStats.pending} 待审核</span>
                    <span>{selectedGroupStats.needsChanges} 需修改</span>
                  </div>
                )}
              </div>
              <div className="review-stage-tools">
                <StatusBadge value={selected.review_status} />
                <button
                  className="secondary-action"
                  type="button"
                  onClick={downloadApprovedPackage}
                  disabled={!selectedGroup.outputs[0]?.production_run_id || busy}
                >
                  打包一键下载
                </button>
                <button
                  className="secondary-action"
                  type="button"
                  onClick={onOpenPackages}
                  disabled={!selectedGroupStats?.approved}
                >
                  创建投放包
                </button>
              </div>
            </div>
            <div className="review-revision-note">
              <strong>版本关系</strong>
              <span>
                当前为 R{selected.revision_number}。标记批次需再生产后，下一轮会生成 R{selected.revision_number + 1}，
                本轮反馈会继续保留用于对照。
              </span>
            </div>

            <div className="variant-strip">
              {selectedGroup.outputs.map((output, index) => (
                <button
                  key={output.output_id}
                  className={`variant-chip ${
                    selected.output_id === output.output_id ? 'selected-variant' : ''
                  }`}
                  onClick={() => selectOutput(output)}
                >
                  <span>{index + 1}. {templateLabel(output)}</span>
                  <StatusBadge value={output.review_status} />
                </button>
              ))}
            </div>

            <video className="video-preview" src={outputFileUrl(selected.output_id)} controls />

            <div className="source-reference">
              <div>
                <h3>原素材参考</h3>
                <video className="compare-video" src={assetFileUrl(selected.asset_id)} controls />
              </div>
              <dl className="metadata-grid">
                <div>
                  <dt>生产意图</dt>
                  <dd>{textValue(selected.creative_goal.title) || selected.template_name}</dd>
                </div>
                <div>
                  <dt>适用场景</dt>
                  <dd>{textValue(selected.production_contract.use_case) || '-'}</dd>
                </div>
                <div>
                  <dt>时长</dt>
                  <dd>{selected.duration_seconds?.toFixed(2) ?? '-'}s</dd>
                </div>
                <div>
                  <dt>文件大小</dt>
                  <dd>{formatBytes(selected.file_size_bytes)}</dd>
                </div>
                <div>
                  <dt>输出编号</dt>
                  <dd>#{selected.output_id}</dd>
                </div>
                <div>
                  <dt>任务名</dt>
                  <dd>{selected.task_name}</dd>
                </div>
              </dl>
            </div>

            <div className="review-contract">
              <h3>审核清单</h3>
              <ul>
                {checklist(selected.production_contract).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="review-contract">
              <div className="panel-header compact-header">
                <h3>Render Plan</h3>
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() => setShowRenderPlan((current) => !current)}
                >
                  {showRenderPlan ? '收起' : '查看'}
                </button>
              </div>
              <div className="render-plan-summary">
                <span>{clipCount(selected.render_plan)} clips</span>
                <span>{outputSummary(selected.render_plan)}</span>
                <span>{fitSummary(selected.render_plan)}</span>
              </div>
              {showRenderPlan && <JsonBlock value={selected.render_plan} />}
            </div>
          </>
        ) : (
          <p className="empty-state">暂无待审核批次。</p>
        )}
      </div>

      <div className="panel review-decision-panel">
        {selected ? (
          <>
            <div className="panel-kicker">审核决策</div>
            <h2>反馈</h2>
            <label>
              反馈或通过说明
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                rows={4}
                placeholder="说明为什么通过、需要修改什么，或为什么丢弃。"
              />
            </label>
            <div className="review-feedback-grid">
              <label>
                审核人
                <input
                  value={reviewerName}
                  onChange={(event) => setReviewerName(event.target.value)}
                  placeholder="运营人员姓名"
                />
              </label>
              <label>
                优先级
                <select value={priority} onChange={(event) => setPriority(event.target.value)}>
                  <option value="">不设置</option>
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                </select>
              </label>
              <label>
                标签
                <input
                  value={tags}
                  onChange={(event) => setTags(event.target.value)}
                  placeholder="钩子, 裁切, 节奏"
                />
              </label>
            </div>
            <div className="structured-feedback-panel">
              <div className="section-title-row">
                <div>
                  <h3>结构化修改原因</h3>
                  <p>点选常用问题，也可以手动补充多条要求；保存后会进入本轮审核反馈。</p>
                </div>
                <button className="secondary-action" type="button" onClick={addBlankChangeRequest}>
                  手动添加
                </button>
              </div>
              <div className="feedback-reason-bank">
                {feedbackReasonPresets.map((preset) => (
                  <button
                    key={`${preset.category}-${preset.target}-${preset.request}`}
                    type="button"
                    className="reason-chip"
                    onClick={() => addPresetChangeRequest(preset)}
                  >
                    {shortReasonLabel(preset)}
                  </button>
                ))}
              </div>
              {changeRequests.length === 0 ? (
                <p className="empty-state">如果选择“要求修改”或“拒绝”，建议至少添加一个结构化原因。</p>
              ) : (
                <div className="change-request-list">
                  {changeRequests.map((request, index) => (
                    <article key={request.id} className="change-request-card">
                      <div className="change-request-fields">
                        <label>
                          类型
                          <select
                            value={request.category}
                            onChange={(event) =>
                              updateChangeRequest(index, { category: event.target.value })
                            }
                          >
                            {changeCategories.map((category) => (
                              <option key={category.value} value={category.value}>
                                {category.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          对象
                          <input
                            value={request.target}
                            onChange={(event) =>
                              updateChangeRequest(index, { target: event.target.value })
                            }
                            placeholder="开头字幕、第三段、背景音乐"
                          />
                        </label>
                        <label>
                          优先级
                          <select
                            value={request.priority}
                            onChange={(event) =>
                              updateChangeRequest(index, { priority: event.target.value })
                            }
                          >
                            <option value="">不设置</option>
                            <option value="low">低</option>
                            <option value="medium">中</option>
                            <option value="high">高</option>
                          </select>
                        </label>
                      </div>
                      <label>
                        修改要求
                        <textarea
                          value={request.request}
                          onChange={(event) =>
                            updateChangeRequest(index, { request: event.target.value })
                          }
                          rows={3}
                          placeholder="记录下一版渲染需要执行的具体修改。"
                        />
                      </label>
                      <button
                        className="secondary-action danger-action"
                        type="button"
                        onClick={() => removeChangeRequest(index)}
                      >
                        删除
                      </button>
                    </article>
                  ))}
                </div>
              )}
            </div>
            {selected.reviewed_at && (
              <p className="notice">
                最近审核：{new Date(selected.reviewed_at).toLocaleString()}
              </p>
            )}
            {selectedGroup?.status === 'needs_revision' && (
              <p className="notice">当前批次已标记为需要再生产。</p>
            )}
            <div className="review-actions">
              <button
                className="secondary-action"
                type="button"
                onClick={markGroupNeedsRevision}
                disabled={
                  !selectedGroup?.outputs[0]?.production_run_id ||
                  selectedGroup.status === 'needs_revision' ||
                  busy
                }
              >
                标记批次需再生产
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() => selectOutput(nextPendingOutput)}
                disabled={!nextPendingOutput || busy}
              >
                下一个待审核
              </button>
              {reviewActions.map((action) => (
                <button
                  key={action.status}
                  className={action.status === 'approved' ? 'primary-action' : 'secondary-action'}
                  title={action.helper}
                  onClick={() => updateReview(action.status)}
                  disabled={busy}
                >
                  {action.label}
                </button>
              ))}
            </div>
          </>
        ) : (
          <p className="empty-state">请选择一个批次和变体进行审核。</p>
        )}
      </div>
    </section>
  );
}

function normalizedChangeRequests(requests: ChangeRequestDraft[]) {
  return requests
    .map((request) => ({
      category: request.category || 'other',
      request: request.request.trim(),
      target: request.target.trim() || undefined,
      priority: request.priority || undefined
    }))
    .filter((request) => request.request);
}

function shortReasonLabel(preset: Omit<ChangeRequestDraft, 'id'>): string {
  const labels: Record<string, string> = {
    开场文字: '开场弱',
    产品镜头: '产品太晚',
    字幕: '字幕难读',
    配乐: '配乐不合适',
    剪辑节奏: '节奏太慢',
    画面裁切: '裁切挡主体',
    CTA: 'CTA 不明显',
    变体差异: '变化太小',
    事实与权利: '事实/授权风险'
  };
  if (preset.target === '广告感') {
    return preset.request.includes('不像广告') ? '不像广告' : '太像广告';
  }
  return labels[preset.target] ?? preset.target;
}

function groupOutputs(outputs: OutputReview[]): ReviewGroup[] {
  const groups = new Map<string, ReviewGroup>();
  outputs.forEach((output) => {
    const title = batchTitle(output);
    const key = output.production_run_id
      ? `run:${output.production_run_id}`
      : `legacy:${output.asset_id}:${title}`;
    const existing = groups.get(key);
    if (existing) {
      existing.outputs.push(output);
      if (output.created_at > existing.latestCreatedAt) {
        existing.latestCreatedAt = output.created_at;
      }
      return;
    }
    groups.set(key, {
      key,
      title,
      assetId: output.asset_id,
      assetFilename: output.asset_filename,
      status: output.production_run_status,
      latestCreatedAt: output.created_at,
      outputs: [output]
    });
  });
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      outputs: [...group.outputs].sort(compareReviewOutputs)
    }))
    .sort(compareReviewGroups);
}

function compareReviewOutputs(left: OutputReview, right: OutputReview): number {
  const leftPending = left.review_status === 'pending_review' ? 0 : 1;
  const rightPending = right.review_status === 'pending_review' ? 0 : 1;
  if (leftPending !== rightPending) return leftPending - rightPending;
  if (left.revision_number !== right.revision_number) {
    return right.revision_number - left.revision_number;
  }
  return left.template_name.localeCompare(right.template_name);
}

function compareReviewGroups(left: ReviewGroup, right: ReviewGroup): number {
  const leftPending = left.outputs.some((output) => output.review_status === 'pending_review')
    ? 0
    : 1;
  const rightPending = right.outputs.some((output) => output.review_status === 'pending_review')
    ? 0
    : 1;
  if (leftPending !== rightPending) return leftPending - rightPending;
  return right.latestCreatedAt.localeCompare(left.latestCreatedAt);
}

function batchTitle(output: OutputReview): string {
  if (output.production_run_name) {
    return output.production_run_name;
  }
  const templateSuffix = ` - ${output.template_name}`;
  if (output.task_name.endsWith(templateSuffix)) {
    return output.task_name.slice(0, -templateSuffix.length);
  }
  return output.task_name || `${output.asset_filename} 批次`;
}

function nextReviewableOutput(
  outputs: OutputReview[],
  selected: OutputReview | null
): OutputReview | null {
  if (outputs.length === 0) return null;
  const currentIndex = selected
    ? outputs.findIndex((output) => output.output_id === selected.output_id)
    : -1;
  const ordered = [
    ...outputs.slice(Math.max(currentIndex + 1, 0)),
    ...outputs.slice(0, Math.max(currentIndex + 1, 0))
  ];
  return ordered.find((output) => output.review_status === 'pending_review') ?? null;
}

function dominantReviewStatus(outputs: OutputReview[]): string {
  const statuses = outputs.map((output) => output.review_status);
  if (statuses.includes('pending_review')) return 'pending_review';
  if (statuses.includes('needs_changes')) return 'needs_changes';
  if (statuses.every((status) => status === 'approved')) return 'approved';
  if (statuses.includes('rejected')) return 'rejected';
  if (statuses.includes('discarded')) return 'discarded';
  return statuses[0] ?? 'pending_review';
}

function reviewGroupStats(outputs: OutputReview[]) {
  return {
    approved: outputs.filter((output) => output.review_status === 'approved').length,
    pending: outputs.filter((output) => output.review_status === 'pending_review').length,
    needsChanges: outputs.filter((output) => output.review_status === 'needs_changes').length
  };
}

function templateLabel(output: OutputReview): string {
  return textValue(output.creative_goal.title) || output.template_name;
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString();
}

function formatBytes(value: number | null) {
  if (!value) return '-';
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function textValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function checklist(contract: Record<string, unknown>): string[] {
  const items = contract.review_checklist;
  if (!Array.isArray(items)) {
    return ['确认成片可读性、创意表达和投放前审核结论。'];
  }
  const textItems = items.filter(
    (item): item is string => typeof item === 'string' && item.length > 0
  );
  return textItems.length
    ? textItems
    : ['确认成片可读性、创意表达和投放前审核结论。'];
}

function clipCount(plan: Record<string, unknown>): number {
  const clips = plan.clips;
  return Array.isArray(clips) ? clips.length : 0;
}

function outputSummary(plan: Record<string, unknown>): string {
  const output = record(plan.output);
  const width = typeof output.width === 'number' ? output.width : null;
  const height = typeof output.height === 'number' ? output.height : null;
  const fps = typeof output.fps === 'number' ? output.fps : null;
  return [width && height ? `${width}x${height}` : 'source size', fps ? `${fps}fps` : null]
    .filter(Boolean)
    .join(' · ');
}

function fitSummary(plan: Record<string, unknown>): string {
  const layout = record(plan.layout);
  return typeof layout.fit === 'string' ? `fit: ${layout.fit}` : 'fit: original';
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
