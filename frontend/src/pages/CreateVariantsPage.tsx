import { FormEvent, useMemo, useState } from 'react';
import { api } from '../api/client';
import { templateBadge, templateSummary, templateTitle } from '../api/templateDisplay';
import type { Asset, GenerationTask, OutputReview, Template, VariantPreflight } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

type CreateVariantsPageProps = {
  assets: Asset[];
  templates: Template[];
  selectedAssetId: number | null;
  onSelectAsset: (assetId: number) => void;
  onTasksCreated: () => Promise<void>;
  onRendered: () => Promise<void>;
  onGoToReview: () => void;
};

export function CreateVariantsPage({
  assets,
  templates,
  selectedAssetId,
  onSelectAsset,
  onTasksCreated,
  onRendered,
  onGoToReview
}: CreateVariantsPageProps) {
  const [namePrefix, setNamePrefix] = useState('seed-video-variant');
  const [selectedTemplateIds, setSelectedTemplateIds] = useState<number[]>([]);
  const [createdTasks, setCreatedTasks] = useState<GenerationTask[]>([]);
  const [renderedOutputs, setRenderedOutputs] = useState<OutputReview[]>([]);
  const [busy, setBusy] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [templateFilter, setTemplateFilter] = useState('');
  const [mode, setMode] = useState<'tasks' | 'queue'>('queue');
  const [preflight, setPreflight] = useState<VariantPreflight | null>(null);

  const selectedAsset = assets.find((asset) => asset.id === selectedAssetId);
  const filteredTemplates = useMemo(() => {
    const needle = templateFilter.trim().toLowerCase();
    if (!needle) return templates;
    return templates.filter((template) => {
      const haystack = `${template.name} ${templateTitle(template)} ${templateSummary(template)}`.toLowerCase();
      return haystack.includes(needle);
    });
  }, [templates, templateFilter]);

  const selectedTemplates = templates.filter((template) =>
    selectedTemplateIds.includes(template.id)
  );

  function toggleTemplate(templateId: number) {
    setSelectedTemplateIds((current) => {
      const next = current.includes(templateId)
        ? current.filter((id) => id !== templateId)
        : [...current, templateId];
      void refreshPreflight(next);
      return next;
    });
  }

  async function refreshPreflight(nextTemplateIds = selectedTemplateIds) {
    if (!selectedAssetId || nextTemplateIds.length === 0) {
      setPreflight(null);
      return;
    }
    const result = await api.preflightVariants(selectedAssetId, {
      name_prefix: namePrefix,
      template_ids: nextTemplateIds,
      params_json: {}
    });
    setPreflight(result);
  }

  async function createVariants(event: FormEvent) {
    event.preventDefault();
    if (!selectedAssetId || selectedTemplateIds.length === 0) return;
    setBusy(true);
      setStatusMessage('正在创建任务...');
    setError('');
    try {
      const tasks = await api.createBatchTasks({
        name_prefix: namePrefix,
        asset_id: selectedAssetId,
        template_ids: selectedTemplateIds,
        params_json: {}
      });
      setCreatedTasks(tasks);
      setRenderedOutputs([]);
      setStatusMessage(`已创建 ${tasks.length} 个任务。`);
      await onTasksCreated();
      await refreshPreflight();
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建任务失败');
    } finally {
      setBusy(false);
    }
  }

  async function renderVariants() {
    if (!selectedAssetId || selectedTemplateIds.length === 0) return;
    setBusy(true);
    setStatusMessage(
      `正在将 ${selectedTemplateIds.length} 个变体加入渲染队列...`
    );
    setError('');
    try {
      const tasks = await api.enqueueVariants(selectedAssetId, {
        name_prefix: namePrefix,
        template_ids: selectedTemplateIds,
        params_json: {}
      });
      setCreatedTasks(tasks);
      setRenderedOutputs([]);
      setStatusMessage(`已加入 ${tasks.length} 个渲染任务。可前往队列查看进度。`);
      await onRendered();
      await refreshPreflight();
    } catch (err) {
      setError(err instanceof Error ? err.message : '加入渲染队列失败');
    } finally {
      setBusy(false);
    }
  }

  async function submitBatch(event: FormEvent) {
    event.preventDefault();
    if (mode === 'queue') {
      await renderVariants();
    } else {
      await createVariants(event);
    }
  }

  function selectAllFiltered() {
    setSelectedTemplateIds((current) =>
      {
        const next = Array.from(new Set([...current, ...filteredTemplates.map((template) => template.id)]));
        void refreshPreflight(next);
        return next;
      }
    );
  }

  function clearSelection() {
    setSelectedTemplateIds([]);
    setPreflight(null);
  }

  return (
    <section className="workspace-grid production-grid">
      <div className="panel">
        <div className="panel-kicker">变体工厂</div>
        <h2>批量设置</h2>
        <form className="variant-form" onSubmit={submitBatch}>
        <label>
          素材视频
          <select
            value={selectedAssetId ?? ''}
            onChange={(event) => onSelectAsset(Number(event.target.value))}
          >
            <option value="" disabled>
              选择素材
            </option>
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                #{asset.id} {asset.original_filename}
              </option>
            ))}
          </select>
        </label>
        <label>
          变体任务名前缀
          <input
            value={namePrefix}
            onChange={(event) => setNamePrefix(event.target.value)}
          />
        </label>
        <label>
          运行模式
          <select value={mode} onChange={(event) => setMode(event.target.value as 'tasks' | 'queue')}>
            <option value="queue">创建任务并加入渲染队列</option>
            <option value="tasks">仅创建任务</option>
          </select>
        </label>
        <label>
          筛选模板
          <input
            value={templateFilter}
            onChange={(event) => setTemplateFilter(event.target.value)}
            placeholder="按标题、名称、时长、格式搜索"
          />
        </label>
        <div className="button-row">
          <button
            className="secondary-action"
            type="button"
            onClick={selectAllFiltered}
            disabled={filteredTemplates.length === 0}
          >
            选择筛选结果
          </button>
          <button
            className="secondary-action"
            type="button"
            onClick={clearSelection}
            disabled={selectedTemplateIds.length === 0}
          >
            清空
          </button>
        </div>
        <div className="checkbox-grid">
          {filteredTemplates.map((template) => (
            <label key={template.id} className="checkbox-row">
              <input
                type="checkbox"
                checked={selectedTemplateIds.includes(template.id)}
                onChange={() => toggleTemplate(template.id)}
              />
              <span>
                <strong>{templateTitle(template)}</strong>
                <small>
                  {templateBadge(template)} · {templateSummary(template)}
                </small>
              </span>
            </label>
          ))}
        </div>
        <div className="button-row">
          <button
            className="primary-action"
            type="submit"
            disabled={!selectedAssetId || selectedTemplateIds.length === 0 || busy}
          >
            {busy ? '处理中...' : mode === 'queue' ? '批量入队' : '创建任务'}
          </button>
          <button
            className="secondary-action"
            type="button"
            onClick={() => refreshPreflight()}
            disabled={!selectedAssetId || selectedTemplateIds.length === 0 || busy}
          >
            生成前预检
          </button>
          <button className="secondary-action" type="button" onClick={onGoToReview}>
            前往审核
          </button>
        </div>
      </form>
      {statusMessage && <p className="notice">{statusMessage}</p>}
      {error && <p className="error-banner">{error}</p>}
      </div>
      <div className="panel wide">
        <div className="panel-header">
          <div>
            <h2>批量预览</h2>
            <p>
              已选择 {selectedTemplateIds.length} 个模板
              {selectedAsset ? `，素材：${selectedAsset.original_filename}` : ''}
            </p>
          </div>
          {selectedAsset && <StatusBadge value={selectedAsset.status} />}
        </div>
        <div className="batch-metrics">
          <div>
            <span>已选模板</span>
            <strong>{selectedTemplateIds.length}</strong>
          </div>
          <div>
            <span>当前可见</span>
            <strong>{filteredTemplates.length}</strong>
          </div>
          <div>
            <span>模式</span>
            <strong>{mode === 'queue' ? '入队' : '草稿'}</strong>
          </div>
        </div>
        <div className="batch-preview-grid">
          {selectedTemplates.map((template) => (
            <article key={template.id} className="template-item">
              <div className="panel-header">
                <div>
                  <h3>{templateTitle(template)}</h3>
                  <p>
                    {templateBadge(template)} · {templateSummary(template)}
                  </p>
                </div>
                <button className="secondary-action" onClick={() => toggleTemplate(template.id)}>移除</button>
              </div>
            </article>
          ))}
          {selectedTemplates.length === 0 && (
            <p className="empty-state">选择模板后可预览批量任务。</p>
          )}
        </div>
        {preflight && (
          <div className="result-box">
            <h3>生成前预检</h3>
            <div className="preflight-list">
              {preflight.items.map((item) => (
                <article key={item.template_id} className="preflight-item">
                  <strong>{item.title || item.template_name}</strong>
                  <span>
                    {item.output_width && item.output_height
                      ? `${item.output_width}x${item.output_height}`
                      : '原始尺寸'} · {item.fit} · {item.estimated_clip_count} 段
                    {item.estimated_duration_seconds
                      ? ` · 约 ${item.estimated_duration_seconds.toFixed(1)} 秒`
                      : ''}
                  </span>
                  <span>
                    遮盖区域 {item.cover_region_count} 个 · 新文字 {item.text_overlay_count} 个
                    {item.playback_speed ? ` · ${item.playback_speed}x 速度` : ''}
                    {item.mute_audio ? ' · 静音' : ''}
                  </span>
                  {item.warnings.length > 0 && (
                    <small>{item.warnings.join('；')}</small>
                  )}
                </article>
              ))}
            </div>
          </div>
        )}
      {createdTasks.length > 0 && (
        <div className="result-box">
          <h3>已创建任务</h3>
          <ul>
            {createdTasks.map((task) => (
              <li key={task.id}>
                #{task.id} {task.name}
              </li>
            ))}
          </ul>
        </div>
      )}
      {renderedOutputs.length > 0 && (
        <div className="result-box">
          <h3>已渲染成片</h3>
          <ul>
            {renderedOutputs.map((output) => (
              <li key={output.output_id}>
                #{output.output_id} {output.template_name} · {output.review_status}
              </li>
            ))}
          </ul>
        </div>
      )}
      </div>
    </section>
  );
}
