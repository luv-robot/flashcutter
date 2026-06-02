import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { templateBadge, templateSummary, templateTitle } from '../api/templateDisplay';
import type {
  AIAsset,
  Asset,
  GenerationTask,
  ProductionRunPreflight,
  Template,
  VariantPreflight
} from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

type CreateVariantsPageProps = {
  assets: Asset[];
  templates: Template[];
  selectedAssetId: number | null;
  onSelectAsset: (assetId: number) => void;
  openSignal: number;
  onTasksCreated: () => Promise<void>;
  onRendered: () => Promise<void>;
  onGoToReview: () => void;
  onGoToAssets: () => void;
};

type WizardStep = 'mode' | 'videos' | 'templates' | 'params' | 'preflight' | 'queue';
type ProductionMode = 'one_asset_many_templates' | 'many_assets_one_template' | 'many_assets_many_templates';

const wizardSteps: Array<{ id: WizardStep; label: string }> = [
  { id: 'mode', label: '选择方式' },
  { id: 'videos', label: '选择视频' },
  { id: 'templates', label: '选择模板' },
  { id: 'params', label: '本次参数' },
  { id: 'preflight', label: '预检' },
  { id: 'queue', label: '入队' }
];

const productionModes: Array<{
  id: ProductionMode;
  title: string;
  description: string;
  output: string;
}> = [
  {
    id: 'one_asset_many_templates',
    title: '一个视频生成多版',
    description: '单条种子视频做多种模板方法探索。',
    output: '1 个视频 x 多个模板'
  },
  {
    id: 'many_assets_one_template',
    title: '一批视频套同一个模板',
    description: '批量素材统一前后贴片、图片框和品牌包装。',
    output: 'N 个视频 x 1 个模板'
  },
  {
    id: 'many_assets_many_templates',
    title: '多个视频 x 多个模板',
    description: '活动期扩产时批量组合，先预检再入队。',
    output: 'N 个视频 x M 个模板'
  }
];

export function CreateVariantsPage({
  assets,
  templates,
  selectedAssetId,
  onSelectAsset,
  openSignal,
  onTasksCreated,
  onRendered,
  onGoToReview,
  onGoToAssets
}: CreateVariantsPageProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [step, setStep] = useState<WizardStep>('mode');
  const [productionMode, setProductionMode] = useState<ProductionMode>('many_assets_one_template');
  const [namePrefix, setNamePrefix] = useState('batch-video-variant');
  const [selectedTemplateIds, setSelectedTemplateIds] = useState<number[]>([]);
  const [selectedAssetIds, setSelectedAssetIds] = useState<number[]>([]);
  const [templateFilter, setTemplateFilter] = useState('');
  const [assetSearch, setAssetSearch] = useState('');
  const [assetStatus, setAssetStatus] = useState('all');
  const [createdTasks, setCreatedTasks] = useState<GenerationTask[]>([]);
  const [busy, setBusy] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [preflight, setPreflight] = useState<VariantPreflight | null>(null);
  const [matrixPreflight, setMatrixPreflight] = useState<ProductionRunPreflight | null>(null);
  const [clipAssets, setClipAssets] = useState<AIAsset[]>([]);
  const [slotOverrides, setSlotOverrides] = useState<Record<string, number | ''>>({});
  const [outputPresetId, setOutputPresetId] = useState('vertical_9_16_cover');
  const [campaignHeadline, setCampaignHeadline] = useState('');

  const productionAssetIds = productionMode === 'one_asset_many_templates'
    ? selectedAssetId ? [selectedAssetId] : []
    : selectedAssetIds;
  const selectedAsset = assets.find((asset) => asset.id === productionAssetIds[0]);
  const selectedTemplates = templates.filter((template) => selectedTemplateIds.includes(template.id));
  const filteredTemplates = useMemo(() => {
    const needle = templateFilter.trim().toLowerCase();
    if (!needle) return templates;
    return templates.filter((template) => {
      const haystack = `${template.name} ${templateTitle(template)} ${templateSummary(template)}`.toLowerCase();
      return haystack.includes(needle);
    });
  }, [templates, templateFilter]);
  const filteredAssets = useMemo(() => {
    const needle = assetSearch.trim().toLowerCase();
    return assets.filter((asset) => {
      const statusMatches = assetStatus === 'all' || asset.status === assetStatus;
      const textMatches =
        !needle ||
        `${asset.id} ${asset.original_filename} ${asset.status}`.toLowerCase().includes(needle);
      return statusMatches && textMatches;
    });
  }, [assets, assetSearch, assetStatus]);
  const preflightTemplateIds = selectedTemplateIds.length > 0
    ? selectedTemplateIds
    : filteredTemplates.map((template) => template.id);
  const canPreflight = productionAssetIds.length > 0 && preflightTemplateIds.length > 0 && !busy;
  const preflightSummary = summarizePreflight(preflight, matrixPreflight);
  const canQueue =
    productionAssetIds.length > 0 &&
    selectedTemplateIds.length > 0 &&
    !busy &&
    preflightSummary.taskCount > 0 &&
    preflightSummary.blockedCount === 0;

  const variantParams = useMemo(() => {
    const bindings = Object.entries(slotOverrides).reduce<Record<string, { source_type: string; asset_id: number }>>(
      (result, [slot, assetId]) => {
        if (assetId) result[slot] = { source_type: 'ai_asset', asset_id: Number(assetId) };
        return result;
      },
      {}
    );
    return Object.keys(bindings).length > 0
      ? { recipe: { slot_bindings: bindings } }
      : {};
  }, [slotOverrides]);

  useEffect(() => {
    if (openSignal > 0) {
      setDialogOpen(true);
      setStep('mode');
    }
  }, [openSignal]);

  useEffect(() => {
    void api.listAIAssets({ asset_kind: 'video', scope: 'private' })
      .then(setClipAssets)
      .catch(() => setClipAssets([]));
  }, []);

  useEffect(() => {
    if (selectedAssetId && selectedAssetIds.length === 0) {
      setSelectedAssetIds([selectedAssetId]);
    }
  }, [selectedAssetId, selectedAssetIds.length]);

  function selectProductionMode(nextMode: ProductionMode) {
    setProductionMode(nextMode);
    setPreflight(null);
    setMatrixPreflight(null);
    if (nextMode === 'many_assets_one_template' && selectedTemplateIds.length > 1) {
      setSelectedTemplateIds([selectedTemplateIds[0]]);
    }
  }

  function toggleAsset(assetId: number) {
    setSelectedAssetIds((current) =>
      current.includes(assetId)
        ? current.filter((id) => id !== assetId)
        : [...current, assetId]
    );
    onSelectAsset(assetId);
    setPreflight(null);
    setMatrixPreflight(null);
  }

  function chooseSingleAsset(assetId: number) {
    onSelectAsset(assetId);
    setSelectedAssetIds([assetId]);
    setPreflight(null);
    setMatrixPreflight(null);
  }

  function toggleTemplate(templateId: number) {
    setSelectedTemplateIds((current) => {
      const next = productionMode === 'many_assets_one_template'
        ? current.includes(templateId) ? [] : [templateId]
        : current.includes(templateId)
          ? current.filter((id) => id !== templateId)
          : [...current, templateId];
      setPreflight(null);
      setMatrixPreflight(null);
      return next;
    });
  }

  function selectAllFilteredTemplates() {
    setSelectedTemplateIds((current) => {
      const next = productionMode === 'many_assets_one_template'
        ? filteredTemplates[0] ? [filteredTemplates[0].id] : []
        : Array.from(new Set([...current, ...filteredTemplates.map((template) => template.id)]));
      setPreflight(null);
      setMatrixPreflight(null);
      return next;
    });
  }

  async function refreshPreflight(nextTemplateIds = preflightTemplateIds) {
    if (productionAssetIds.length === 0 || nextTemplateIds.length === 0) {
      setPreflight(null);
      setMatrixPreflight(null);
      return;
    }
    setBusy(true);
    setError('');
    try {
      if (productionMode === 'one_asset_many_templates' && selectedAssetId) {
        const result = await api.preflightVariants(selectedAssetId, {
          name_prefix: namePrefix,
          template_ids: nextTemplateIds,
          params_json: variantParams
        });
        setPreflight(result);
        setMatrixPreflight(null);
        setStatusMessage(`已完成 ${result.items.length} 个变体预检。`);
      } else {
        const result = await api.preflightProductionRun({
          asset_ids: productionAssetIds,
          template_ids: nextTemplateIds,
          runtime_values: productionRuntimeValues(),
          output_preset_id: outputPresetId,
          name_prefix: namePrefix
        });
        setMatrixPreflight(result);
        setPreflight(null);
        setStatusMessage(
          `已完成 ${result.summary.task_count} 个组合预检，${result.summary.blocked_count} 个需要处理。`
        );
      }
      setStep('preflight');
    } catch (err) {
      setError(err instanceof Error ? err.message : '预检失败');
    } finally {
      setBusy(false);
    }
  }

  async function createDraftTasks() {
    if (!selectedAssetId || selectedTemplateIds.length === 0) return;
    setBusy(true);
    setStatusMessage('正在创建任务...');
    setError('');
    try {
      const tasks = await api.createBatchTasks({
        name_prefix: namePrefix,
        asset_id: selectedAssetId,
        template_ids: selectedTemplateIds,
        params_json: variantParams
      });
      setCreatedTasks(tasks);
      setStatusMessage(`已创建 ${tasks.length} 个任务。`);
      await onTasksCreated();
      setStep('queue');
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建任务失败');
    } finally {
      setBusy(false);
    }
  }

  async function renderVariants() {
    if (productionAssetIds.length === 0 || selectedTemplateIds.length === 0) return;
    setBusy(true);
    setStatusMessage(`正在将 ${productionAssetIds.length * selectedTemplateIds.length} 个变体加入渲染队列...`);
    setError('');
    try {
      const tasks = productionMode === 'one_asset_many_templates' && selectedAssetId
        ? await api.enqueueVariants(selectedAssetId, {
            name_prefix: namePrefix,
            template_ids: selectedTemplateIds,
            params_json: variantParams
          })
        : await api.enqueueProductionRun({
            asset_ids: productionAssetIds,
            template_ids: selectedTemplateIds,
            runtime_values: productionRuntimeValues(),
            output_preset_id: outputPresetId,
            name_prefix: namePrefix,
            preflight_token: matrixPreflight?.preflight_token
          });
      setCreatedTasks(tasks);
      setStatusMessage(`已加入 ${tasks.length} 个渲染任务。完成后会提醒你去审核。`);
      await onRendered();
      setStep('queue');
    } catch (err) {
      setError(err instanceof Error ? err.message : '加入渲染队列失败');
    } finally {
      setBusy(false);
    }
  }

  function productionRuntimeValues() {
    return {
      ...(campaignHeadline.trim() ? { campaign_headline: campaignHeadline.trim() } : {})
    };
  }

  function nextStep() {
    const index = wizardSteps.findIndex((item) => item.id === step);
    const next = wizardSteps[Math.min(wizardSteps.length - 1, index + 1)];
    setStep(next.id);
  }

  function previousStep() {
    const index = wizardSteps.findIndex((item) => item.id === step);
    const previous = wizardSteps[Math.max(0, index - 1)];
    setStep(previous.id);
  }

  function stepReady(stepId: WizardStep) {
    if (stepId === 'mode') return true;
    if (stepId === 'videos') return productionAssetIds.length > 0;
    if (stepId === 'templates') return selectedTemplateIds.length > 0;
    if (stepId === 'params') return Boolean(namePrefix.trim());
    if (stepId === 'preflight') return preflightSummary.taskCount > 0;
    if (stepId === 'queue') return createdTasks.length > 0;
    return false;
  }

  return (
    <section className="production-page">
      <div className="workflow-hero panel">
        <div>
          <div className="panel-kicker">生产批次</div>
          <h2>一口气完成批量生产配置</h2>
          <p>选择生产方式、视频、模板方法、本次参数，预检通过后加入队列。</p>
        </div>
        <button className="primary-action" type="button" onClick={() => setDialogOpen(true)}>
          创建生产批次
        </button>
      </div>

      <div className="panel workflow-status-panel">
        <div className="batch-metrics">
          <div>
            <span>可用素材</span>
            <strong>{assets.length}</strong>
          </div>
          <div>
            <span>模板方法</span>
            <strong>{templates.length}</strong>
          </div>
          <div>
            <span>可用片段</span>
            <strong>{clipAssets.length}</strong>
          </div>
        </div>
        <p className="muted-copy">当前默认流程：一批视频套同一个模板。</p>
      </div>

      {dialogOpen && (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel workflow-modal production-wizard-modal" role="dialog" aria-modal="true">
            <div className="modal-header">
              <div>
                <div className="panel-kicker">创建生产批次</div>
                <h2>{wizardSteps.find((item) => item.id === step)?.label}</h2>
                <p>任何一步失败后都可以返回修改，也可以重新发起。</p>
              </div>
              <button className="secondary-action" type="button" onClick={() => setDialogOpen(false)}>
                关闭
              </button>
            </div>

            <div className="workflow-steps" aria-label="生产步骤">
              {wizardSteps.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`${step === item.id ? 'current-step' : ''} ${stepReady(item.id) ? 'step-ready' : ''}`}
                  onClick={() => setStep(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <div className="wizard-body">
              {step === 'mode' && (
                <div className="mode-card-grid">
                  {productionModes.map((mode) => (
                    <button
                      key={mode.id}
                      type="button"
                      className={`mode-card ${productionMode === mode.id ? 'selected-mode-card' : ''}`}
                      onClick={() => selectProductionMode(mode.id)}
                    >
                      <strong>{mode.title}</strong>
                      <span>{mode.description}</span>
                      <small>{mode.output}</small>
                    </button>
                  ))}
                </div>
              )}

              {step === 'videos' && (
                <div className="wizard-split">
                  <aside className="wizard-filter-panel">
                    <label>
                      关键词
                      <input
                        value={assetSearch}
                        onChange={(event) => setAssetSearch(event.target.value)}
                        placeholder="搜索文件名"
                      />
                    </label>
                    <label>
                      状态
                      <select value={assetStatus} onChange={(event) => setAssetStatus(event.target.value)}>
                        <option value="all">全部</option>
                        <option value="ready">可用</option>
                        <option value="uploaded">已上传</option>
                        <option value="failed">失败</option>
                      </select>
                    </label>
                    <button className="secondary-action" type="button" onClick={onGoToAssets}>
                      批量导入
                    </button>
                  </aside>
                  <div className="asset-pick-grid">
                    {filteredAssets.map((asset) => {
                      const checked = productionMode === 'one_asset_many_templates'
                        ? selectedAssetId === asset.id
                        : selectedAssetIds.includes(asset.id);
                      return (
                        <label key={asset.id} className="asset-pick-card">
                          <input
                            type={productionMode === 'one_asset_many_templates' ? 'radio' : 'checkbox'}
                            checked={checked}
                            onChange={() =>
                              productionMode === 'one_asset_many_templates'
                                ? chooseSingleAsset(asset.id)
                                : toggleAsset(asset.id)
                            }
                          />
                          <span className="asset-thumb">MP4</span>
                          <strong>{asset.original_filename}</strong>
                          <small>
                            #{asset.id} · {asset.status} · {new Date(asset.created_at).toLocaleDateString()}
                          </small>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}

              {step === 'templates' && (
                <div className="template-picker-view">
                  <div className="template-filter-row">
                    <input
                      value={templateFilter}
                      onChange={(event) => setTemplateFilter(event.target.value)}
                      placeholder="按名称、目标、时长、格式搜索"
                    />
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={selectAllFilteredTemplates}
                      disabled={filteredTemplates.length === 0}
                    >
                      {productionMode === 'many_assets_one_template' ? '选择第一个结果' : '选择筛选结果'}
                    </button>
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => setSelectedTemplateIds([])}
                      disabled={selectedTemplateIds.length === 0}
                    >
                      清空
                    </button>
                  </div>
                  <div className="template-method-grid">
                    {filteredTemplates.map((template) => (
                      <label key={template.id} className="template-method-card">
                        <input
                          type={productionMode === 'many_assets_one_template' ? 'radio' : 'checkbox'}
                          checked={selectedTemplateIds.includes(template.id)}
                          onChange={() => toggleTemplate(template.id)}
                        />
                        <span>{templateBadge(template)}</span>
                        <strong>{templateTitle(template)}</strong>
                        <small>会执行：{templateSummary(template)}</small>
                        <small>适用场景：{template.description || '通用广告变体'}</small>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {step === 'params' && (
                <div className="runtime-param-grid">
                  <label>
                    变体任务名前缀
                    <input value={namePrefix} onChange={(event) => setNamePrefix(event.target.value)} />
                  </label>
                  <label>
                    输出规格
                    <select value={outputPresetId} onChange={(event) => setOutputPresetId(event.target.value)}>
                      <option value="vertical_9_16_cover">竖版 9:16 填满画面</option>
                      <option value="vertical_9_16_contain">竖版 9:16 保留完整画面</option>
                      <option value="square_1_1_contain">方版 1:1</option>
                      <option value="horizontal_16_9_cover">横版 16:9</option>
                      <option value="source_original">保持原尺寸</option>
                    </select>
                  </label>
                  <label>
                    本次活动文案
                    <input
                      value={campaignHeadline}
                      onChange={(event) => setCampaignHeadline(event.target.value)}
                      placeholder="只保存到本次生产批次"
                    />
                  </label>
                  <label>
                    Hook 片段
                    <select
                      value={slotOverrides.hook ?? ''}
                      onChange={(event) =>
                        setSlotOverrides((current) => ({
                          ...current,
                          hook: event.target.value ? Number(event.target.value) : ''
                        }))
                      }
                    >
                      <option value="">自动匹配</option>
                      {clipAssets.filter((clip) => clip.asset_type === 'hook').map((clip) => (
                        <option key={clip.id} value={clip.id}>
                          #{clip.id} {clip.title} · {formatDuration(clip.duration_seconds)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    CTA / Reaction 片段
                    <select
                      value={slotOverrides.cta ?? ''}
                      onChange={(event) =>
                        setSlotOverrides((current) => ({
                          ...current,
                          cta: event.target.value ? Number(event.target.value) : ''
                        }))
                      }
                    >
                      <option value="">自动匹配</option>
                      {clipAssets.filter((clip) => ['cta', 'reaction'].includes(clip.asset_type)).map((clip) => (
                        <option key={clip.id} value={clip.id}>
                          #{clip.id} {clip.title} · {labelForType(clip.asset_type)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="one-time-note">
                    这些内容只保存到本次生产批次，不会写入模板方法。
                  </div>
                </div>
              )}

              {step === 'preflight' && (
                <div className="preflight-workbench">
                  <div className="preflight-summary-grid">
                    <SummaryTile label="将创建" value={`${preflightSummary.taskCount} 个任务`} />
                    <SummaryTile label="可入队" value={`${preflightSummary.readyCount} 个`} />
                    <SummaryTile label="需要处理" value={`${preflightSummary.blockedCount} 个`} tone={preflightSummary.blockedCount ? 'danger' : 'neutral'} />
                    <SummaryTile label="预计渲染" value={preflightSummary.estimatedText} />
                  </div>
                  {preflightSummary.blockedCount > 0 && (
                    <div className="functional-error">
                      <strong>这批任务还不能入队</strong>
                      <p>原因：有任务缺少模板要求的本次参数或素材。先处理阻塞项，再重新预检。</p>
                      <div className="button-row">
                        <button className="secondary-action" type="button" onClick={() => setStep('params')}>
                          返回补参数
                        </button>
                        <button className="secondary-action" type="button" onClick={() => setStep('templates')}>
                          改用其他模板
                        </button>
                        <button className="secondary-action" type="button" onClick={() => setDialogOpen(false)}>
                          暂存草稿
                        </button>
                      </div>
                    </div>
                  )}
                  <div className="preflight-list">
                    {preflightSummary.items.length === 0 ? (
                      <p className="empty-state">点击“运行预检”后查看任务是否可入队。</p>
                    ) : (
                      preflightSummary.items.map((item, index) => (
                        <article key={`${item.asset_id}-${item.template_id}-${index}`} className="preflight-item">
                          <strong>{item.asset_filename || selectedAsset?.original_filename || '当前视频'} / {item.title || item.template_name}</strong>
                          <span>
                            {preflightStatusLabel(item.status, item.missing_fields)} ·{' '}
                            {item.output_width && item.output_height
                              ? `${item.output_width}x${item.output_height}`
                              : '原始尺寸'} · {item.fit}
                          </span>
                          {item.missing_fields.length > 0 && <small>缺少：{item.missing_fields.join('、')}</small>}
                          {item.warnings.length > 0 && <small>{item.warnings.join('；')}</small>}
                        </article>
                      ))
                    )}
                  </div>
                </div>
              )}

              {step === 'queue' && (
                <div className="queue-confirmation">
                  <div className="result-box">
                    <h3>本次批次</h3>
                    <p>
                      {productionAssetIds.length} 个视频 · {selectedTemplateIds.length} 个模板 ·{' '}
                      {productionAssetIds.length * selectedTemplateIds.length} 个任务
                    </p>
                  </div>
                  <div className="created-task-grid">
                    {createdTasks.length === 0 ? (
                      <p className="empty-state">点击“批量入队”后，任务会进入队列与失败页。</p>
                    ) : (
                      createdTasks.map((task) => (
                        <article key={task.id} className="created-task-card">
                          <div>
                            <strong>#{task.id} {task.name}</strong>
                            <span>{task.progress_message || '已创建'}</span>
                          </div>
                          <StatusBadge value={task.status} />
                        </article>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {statusMessage && <p className="notice">{statusMessage}</p>}
            {error && (
              <div className="action-error">
                <strong>这一步没有完成</strong>
                <p>{error}</p>
                <div className="button-row">
                  <button className="secondary-action" type="button" onClick={() => refreshPreflight(preflightTemplateIds)} disabled={!canPreflight}>
                    重新预检
                  </button>
                  <button className="secondary-action" type="button" onClick={onGoToAssets}>
                    去补充素材
                  </button>
                </div>
              </div>
            )}

            <div className="wizard-footer">
              <div className="wizard-selection-summary">
                已选 {productionAssetIds.length} 个视频 · {selectedTemplateIds.length} 个模板
              </div>
              <div className="button-row">
                <button className="secondary-action" type="button" onClick={previousStep} disabled={step === 'mode' || busy}>
                  上一步
                </button>
                {step !== 'preflight' && step !== 'queue' && (
                  <button
                    className="primary-action"
                    type="button"
                    onClick={nextStep}
                    disabled={
                      busy ||
                      (step === 'videos' && productionAssetIds.length === 0) ||
                      (step === 'templates' && selectedTemplateIds.length === 0)
                    }
                  >
                    下一步
                  </button>
                )}
                {step === 'preflight' && (
                  <>
                    <button className="secondary-action" type="button" onClick={() => refreshPreflight(preflightTemplateIds)} disabled={!canPreflight}>
                      {busy ? '预检中...' : '运行预检'}
                    </button>
                    <button className="primary-action" type="button" onClick={() => setStep('queue')} disabled={!canQueue}>
                      前往入队
                    </button>
                  </>
                )}
                {step === 'queue' && (
                  <>
                    <button className="secondary-action" type="button" onClick={createDraftTasks} disabled={busy || productionMode !== 'one_asset_many_templates' || selectedTemplateIds.length === 0}>
                      仅创建任务
                    </button>
                    <button className="primary-action" type="button" onClick={renderVariants} disabled={!canQueue}>
                      {busy ? '入队中...' : '批量入队'}
                    </button>
                    <button className="secondary-action" type="button" onClick={onGoToReview}>
                      前往审核
                    </button>
                  </>
                )}
              </div>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function SummaryTile({
  label,
  value,
  tone = 'neutral'
}: {
  label: string;
  value: string;
  tone?: 'neutral' | 'danger';
}) {
  return (
    <div className={`summary-tile summary-tile-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function summarizePreflight(
  preflight: VariantPreflight | null,
  matrixPreflight: ProductionRunPreflight | null
) {
  const items = matrixPreflight?.items ?? preflight?.items ?? [];
  const taskCount = matrixPreflight?.summary.task_count ?? items.length;
  const readyCount =
    matrixPreflight
      ? matrixPreflight.summary.ready_count + matrixPreflight.summary.warning_count
      : items.filter((item) => item.status !== 'blocked' && item.missing_fields.length === 0).length;
  const blockedCount =
    matrixPreflight?.summary.blocked_count ??
    items.filter((item) => item.status === 'blocked' || item.missing_fields.length > 0).length;
  const estimatedSeconds = items.reduce((total, item) => {
    return total + (item.estimated_duration_seconds ?? 0);
  }, 0);
  return {
    items,
    taskCount,
    readyCount,
    blockedCount,
    estimatedText: estimatedSeconds ? `约 ${Math.ceil(estimatedSeconds / 60)} 分钟` : '待预检'
  };
}

function preflightStatusLabel(status: string, missingFields: string[]) {
  if (status === 'blocked' || missingFields.length > 0) return '需处理';
  if (status === 'warning') return '可入队，有提醒';
  return '可入队';
}

function labelForType(value: string) {
  const labels: Record<string, string> = {
    hook: 'Hook',
    cta: 'CTA',
    broll: 'B-roll',
    reaction: 'Reaction',
    meme: 'Meme',
    product_motion: 'Product motion'
  };
  return labels[value] ?? value;
}

function formatDuration(value: number | null) {
  return value ? `${value.toFixed(1)}s` : '时长未知';
}
