import { useEffect, useState } from 'react';
import { api, assetFileUrl, outputFileUrl } from '../api/client';
import type { Asset, OutputReview } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

type ReviewOutputsPageProps = {
  outputs: OutputReview[];
  assets: Asset[];
  focusedAssetId: number | null;
  onRefresh: () => Promise<void>;
};

const reviewActions = [
  {
    status: 'approved',
    label: '通过',
    helper: '保留该成片用于投放测试。'
  },
  {
    status: 'needs_changes',
    label: '要求修改',
    helper: '记录反馈，用于生成下一版变体。'
  },
  {
    status: 'discarded',
    label: '丢弃',
    helper: '从可用成片集合中移除。'
  },
  {
    status: 'rejected',
    label: '拒绝',
    helper: '标记为已审核但不可用。'
  }
];

export function ReviewOutputsPage({
  outputs,
  assets,
  focusedAssetId,
  onRefresh
}: ReviewOutputsPageProps) {
  const [assetFilter, setAssetFilter] = useState<number | 'all'>(focusedAssetId ?? 'all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const filteredOutputs =
    outputs.filter((output) => {
      const assetMatches = assetFilter === 'all' || output.asset_id === assetFilter;
      const statusMatches = statusFilter === 'all' || output.review_status === statusFilter;
      return assetMatches && statusMatches;
    });
  const [selected, setSelected] = useState<OutputReview | null>(outputs[0] ?? null);
  const [notes, setNotes] = useState(selected?.review_notes ?? '');
  const [reviewerName, setReviewerName] = useState('');
  const [changeRequest, setChangeRequest] = useState('');
  const [priority, setPriority] = useState('');
  const [tags, setTags] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (focusedAssetId) {
      setAssetFilter(focusedAssetId);
    }
  }, [focusedAssetId]);

  useEffect(() => {
    const nextSelected =
      filteredOutputs.find((output) => output.output_id === selected?.output_id) ??
      filteredOutputs[0] ??
      null;
    setSelected(nextSelected);
    setNotes(nextSelected?.review_notes ?? '');
    hydrateFeedback(nextSelected);
  }, [assetFilter, outputs]);

  function selectOutput(output: OutputReview) {
    setSelected(output);
    setNotes(output.review_notes ?? '');
    hydrateFeedback(output);
  }

  function hydrateFeedback(output: OutputReview | null) {
    const feedback = output?.review_feedback ?? {};
    setReviewerName(String(feedback.reviewer_name ?? ''));
    setChangeRequest(String(feedback.change_request ?? ''));
    setPriority(String(feedback.priority ?? ''));
    setTags(Array.isArray(feedback.tags) ? feedback.tags.join(', ') : '');
  }

  async function updateReview(reviewStatus: string) {
    if (!selected) return;
    setBusy(true);
    try {
      const updated = await api.updateOutputReview(selected.output_id, {
        review_status: reviewStatus,
        review_notes: notes,
        reviewer_name: reviewerName || undefined,
        change_request: changeRequest || undefined,
        priority: priority || undefined,
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean)
      });
      setSelected(updated);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="review-layout">
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">审核收件箱</div>
            <h2>成片版本</h2>
          </div>
          <button className="secondary-action" onClick={onRefresh}>刷新</button>
        </div>
        <label>
          素材筛选
          <select
            value={assetFilter}
            onChange={(event) =>
              setAssetFilter(
                event.target.value === 'all' ? 'all' : Number(event.target.value)
              )
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
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">全部状态</option>
            <option value="pending_review">待审核</option>
            <option value="approved">已通过</option>
            <option value="needs_changes">需修改</option>
            <option value="rejected">已拒绝</option>
            <option value="discarded">已丢弃</option>
          </select>
        </label>
        <div className="output-list">
          {filteredOutputs.map((output) => (
          <button
              key={output.output_id}
              className={`output-row ${
                selected?.output_id === output.output_id ? 'selected-output' : ''
              }`}
              onClick={() => selectOutput(output)}
            >
              <span>#{output.output_id} {output.task_name}</span>
              <StatusBadge value={output.review_status} />
            </button>
          ))}
        </div>
      </div>
      <div className="panel wide review-stage">
        {selected ? (
          <>
            <div className="panel-header">
              <div>
                <h2>{selected.task_name}</h2>
                <p>
                  {selected.asset_filename} · {selected.template_name} v
                  {selected.template_version}
                </p>
              </div>
              <StatusBadge value={selected.status} />
            </div>
            <video
              className="video-preview"
              src={outputFileUrl(selected.output_id)}
              controls
            />
            <div className="source-compare-grid">
              <div>
                <h3>原素材</h3>
                <video
                  className="compare-video"
                  src={assetFileUrl(selected.asset_id)}
                  controls
                />
              </div>
              <div>
                <h3>生成成片</h3>
                <video
                  className="compare-video"
                  src={outputFileUrl(selected.output_id)}
                  controls
                />
              </div>
            </div>
            <dl className="metadata-grid">
              <div>
                <dt>时长</dt>
                <dd>{selected.duration_seconds?.toFixed(2) ?? '-'}s</dd>
              </div>
              <div>
                <dt>文件大小</dt>
                <dd>{formatBytes(selected.file_size_bytes)}</dd>
              </div>
              <div>
                <dt>审核</dt>
                <dd>
                  <StatusBadge value={selected.review_status} />
                </dd>
              </div>
              <div>
                <dt>成片路径</dt>
                <dd>{selected.file_path}</dd>
              </div>
            </dl>
          </>
        ) : (
          <p className="empty-state">暂无成片。</p>
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
            <label>
              修改要求
              <textarea
                value={changeRequest}
                onChange={(event) => setChangeRequest(event.target.value)}
                rows={3}
                placeholder="记录下一版渲染需要执行的具体修改。"
              />
            </label>
            {selected.reviewed_at && (
              <p className="notice">
                最近审核：{new Date(selected.reviewed_at).toLocaleString()}
              </p>
            )}
            <div className="review-actions">
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
          <p className="empty-state">请选择一个成片进行审核。</p>
        )}
      </div>
    </section>
  );
}

function formatBytes(value: number | null) {
  if (!value) return '-';
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
