import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { labelForAIAssetType, rightsStatusFromTags } from '../api/assetDisplay';
import { templateBadge, templateSummary, templateTitle } from '../api/templateDisplay';
import type {
  AIAsset,
  Asset,
  GenerationTask,
  MusicTrack,
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
  onGoToQueue: () => void;
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

const DRAFT_KEY = 'flashcutter_production_draft_v1';

type RuntimeField = {
  key: string;
  label: string;
  field_type: string;
  asset_kind?: string;
  asset_type?: string;
  required?: boolean;
  max_length?: number;
};

type RuntimeValue = string | number | { asset_id: number };
type PreflightItem = VariantPreflight['items'][number];

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
  onGoToAssets,
  onGoToQueue
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
  const [imageAssets, setImageAssets] = useState<AIAsset[]>([]);
  const [musicTracks, setMusicTracks] = useState<MusicTrack[]>([]);
  const [slotOverrides, setSlotOverrides] = useState<Record<string, number | ''>>({});
  const [runtimeValues, setRuntimeValues] = useState<Record<string, RuntimeValue>>({});
  const [outputPresetId, setOutputPresetId] = useState('vertical_9_16_cover');
  const [campaignHeadline, setCampaignHeadline] = useState('');
  const [draftAvailable, setDraftAvailable] = useState(() =>
    Boolean(localStorage.getItem(DRAFT_KEY))
  );
  const [namePrefixTouched, setNamePrefixTouched] = useState(false);

  const productionAssetIds = productionMode === 'one_asset_many_templates'
    ? selectedAssetId ? [selectedAssetId] : []
    : selectedAssetIds;
  const selectedAsset = assets.find((asset) => asset.id === productionAssetIds[0]);
  const selectedTemplates = templates.filter((template) => selectedTemplateIds.includes(template.id));
  const runtimeFields = useMemo(
    () => runtimeFieldsForTemplates(selectedTemplates),
    [selectedTemplates]
  );
  const autoNamePrefix = useMemo(
    () => buildAutoNamePrefix(productionMode, productionAssetIds, selectedTemplates, assets),
    [assets, productionAssetIds, productionMode, selectedTemplates]
  );
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
  const groupedPreflight = groupPreflightItems(preflightSummary.items);
  const dynamicRuntimeFields = runtimeFields.filter(
    (field) => !['campaign_headline', 'hook', 'cta'].includes(field.key)
  );
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
    void Promise.all([
      api.listAIAssets({ asset_kind: 'video' }),
      api.listAIAssets({ asset_kind: 'image' }),
      api.listMusic()
    ])
      .then(([clips, images, tracks]) => {
        setClipAssets(clips);
        setImageAssets(images);
        setMusicTracks(tracks);
      })
      .catch(() => {
        setClipAssets([]);
        setImageAssets([]);
        setMusicTracks([]);
      });
  }, []);

  useEffect(() => {
    if (selectedAssetId && selectedAssetIds.length === 0) {
      setSelectedAssetIds([selectedAssetId]);
    }
  }, [selectedAssetId, selectedAssetIds.length]);

  useEffect(() => {
    if (!namePrefixTouched && autoNamePrefix) {
      setNamePrefix(autoNamePrefix);
    }
  }, [autoNamePrefix, namePrefixTouched]);

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
    const dynamicRuntimeValues = Object.entries(runtimeValues).reduce<Record<string, RuntimeValue>>(
      (result, [key, value]) => {
        if (value === '' || value == null) return result;
        result[key] = value;
        return result;
      },
      {}
    );
    Object.entries(slotOverrides).forEach(([slot, assetId]) => {
      if (assetId) {
        dynamicRuntimeValues[slot] = { asset_id: Number(assetId) };
      }
    });
    return {
      ...dynamicRuntimeValues,
      ...(campaignHeadline.trim() ? { campaign_headline: campaignHeadline.trim() } : {})
    };
  }

  function updateRuntimeField(key: string, value: RuntimeValue | '') {
    setRuntimeValues((current) => {
      const next = { ...current };
      if (value === '') {
        delete next[key];
      } else {
        next[key] = value;
      }
      setPreflight(null);
      setMatrixPreflight(null);
      return next;
    });
  }

  function saveDraft() {
    const payload = {
      productionMode,
      namePrefix,
      selectedTemplateIds,
      selectedAssetIds,
      selectedAssetId,
      slotOverrides,
      runtimeValues,
      outputPresetId,
      campaignHeadline
    };
    localStorage.setItem(DRAFT_KEY, JSON.stringify(payload));
    setDraftAvailable(true);
    setStatusMessage('已暂存草稿。下次创建生产批次时可以继续载入。');
    setDialogOpen(false);
  }

  function loadDraft() {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return;
    try {
      const payload = JSON.parse(raw) as {
        productionMode?: ProductionMode;
        namePrefix?: string;
        selectedTemplateIds?: number[];
        selectedAssetIds?: number[];
        selectedAssetId?: number | null;
        slotOverrides?: Record<string, number | ''>;
        runtimeValues?: Record<string, RuntimeValue>;
        outputPresetId?: string;
        campaignHeadline?: string;
      };
      if (payload.productionMode) setProductionMode(payload.productionMode);
      if (payload.namePrefix) {
        setNamePrefix(payload.namePrefix);
        setNamePrefixTouched(true);
      }
      if (payload.selectedTemplateIds) setSelectedTemplateIds(payload.selectedTemplateIds);
      if (payload.selectedAssetIds) setSelectedAssetIds(payload.selectedAssetIds);
      if (payload.selectedAssetId) onSelectAsset(payload.selectedAssetId);
      if (payload.slotOverrides) setSlotOverrides(payload.slotOverrides);
      if (payload.runtimeValues) setRuntimeValues(payload.runtimeValues);
      if (payload.outputPresetId) setOutputPresetId(payload.outputPresetId);
      if (payload.campaignHeadline) setCampaignHeadline(payload.campaignHeadline);
      setPreflight(null);
      setMatrixPreflight(null);
      setStatusMessage('已载入暂存草稿，请重新运行预检后入队。');
      setStep('videos');
    } catch {
      setError('暂存草稿无法读取，请重新选择视频和模板。');
    }
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
        <p className="rights-note">只使用已确认可商用的原始视频、片段、图片和配乐；本次参数不会写回模板方法。</p>
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
                <div className="wizard-stack">
                  {draftAvailable && (
                    <div className="draft-resume-panel">
                      <div>
                        <strong>检测到暂存草稿</strong>
                        <span>可以继续上一次没有入队的批次，载入后需要重新预检。</span>
                      </div>
                      <button className="secondary-action" type="button" onClick={loadDraft}>
                        继续草稿
                      </button>
                    </div>
                  )}
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
                    {filteredAssets.length === 0 ? (
                      <div className="empty-action-state">
                        <p className="empty-state">没有可选视频。先上传或导入一条已授权原始视频。</p>
                        <button className="secondary-action" type="button" onClick={onGoToAssets}>
                          去素材库上传
                        </button>
                      </div>
                    ) : filteredAssets.map((asset) => {
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
                    {filteredTemplates.length === 0 ? (
                      <div className="empty-action-state">
                        <p className="empty-state">没有匹配的模板方法。清空筛选或先创建一个模板方法。</p>
                        <button className="secondary-action" type="button" onClick={() => setTemplateFilter('')}>
                          清空筛选
                        </button>
                      </div>
                    ) : filteredTemplates.map((template) => (
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
                    <div className="inline-field-action">
                      <input
                        value={namePrefix}
                        onChange={(event) => {
                          setNamePrefix(event.target.value);
                          setNamePrefixTouched(true);
                          setPreflight(null);
                          setMatrixPreflight(null);
                        }}
                      />
                      <button
                        className="secondary-action"
                        type="button"
                        onClick={() => {
                          setNamePrefix(autoNamePrefix);
                          setNamePrefixTouched(false);
                        }}
                      >
                        自动命名
                      </button>
                    </div>
                  </label>
                  <label>
                    输出规格
                    <select
                      value={outputPresetId}
                      onChange={(event) => {
                        setOutputPresetId(event.target.value);
                        setPreflight(null);
                        setMatrixPreflight(null);
                      }}
                    >
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
                      onChange={(event) => {
                        setCampaignHeadline(event.target.value);
                        setPreflight(null);
                        setMatrixPreflight(null);
                      }}
                      placeholder="只保存到本次生产批次"
                    />
                  </label>
                  <label>
                    Hook 片段
                    <select
                      value={slotOverrides.hook ?? ''}
                      onChange={(event) => {
                        setSlotOverrides((current) => ({
                          ...current,
                          hook: event.target.value ? Number(event.target.value) : ''
                        }));
                        setPreflight(null);
                        setMatrixPreflight(null);
                      }}
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
                      onChange={(event) => {
                        setSlotOverrides((current) => ({
                          ...current,
                          cta: event.target.value ? Number(event.target.value) : ''
                        }));
                        setPreflight(null);
                        setMatrixPreflight(null);
                      }}
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
                  <div className="one-time-note">
                    如果模板选择配乐，生成视频会用所选配乐替换原视频声音；需要保留原声时请改用不替换配乐的模板。
                  </div>
                  {dynamicRuntimeFields.length > 0 && (
                    <div className="runtime-field-section">
                      <div className="section-title-row">
                        <div>
                          <h3>模板要求的本次字段</h3>
                          <p>这些字段来自已选模板，只影响本批次。</p>
                        </div>
                        <strong>{dynamicRuntimeFields.length}</strong>
                      </div>
                      <div className="runtime-field-grid">
                        {dynamicRuntimeFields.map((field) => (
                          <RuntimeFieldControl
                            key={field.key}
                            field={field}
                            value={runtimeValues[field.key] ?? ''}
                            videoAssets={clipAssets}
                            imageAssets={imageAssets}
                            musicTracks={musicTracks}
                            onChange={(value) => updateRuntimeField(field.key, value)}
                          />
                        ))}
                      </div>
                    </div>
                  )}
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
                        <button className="secondary-action" type="button" onClick={saveDraft}>
                          暂存草稿
                        </button>
                      </div>
                    </div>
                  )}
                  {groupedPreflight.warning.length > 0 && preflightSummary.blockedCount === 0 && (
                    <p className="notice">有提醒项但不阻塞入队，建议审核时重点查看这些变体。</p>
                  )}
                  {preflightSummary.items.length === 0 ? (
                    <p className="empty-state">点击“运行预检”后查看任务是否可入队。</p>
                  ) : (
                    <div className="preflight-status-stack">
                      {(['blocked', 'warning', 'ready'] as const).map((status) => {
                        const items = groupedPreflight[status];
                        if (items.length === 0) return null;
                        return (
                          <section key={status} className={`preflight-status-section preflight-status-${status}`}>
                            <div className="panel-header compact">
                              <div>
                                <h3>{preflightGroupLabel(status)}</h3>
                                <p>{preflightGroupDescription(status)}</p>
                              </div>
                              <strong className="summary-number">{items.length}</strong>
                            </div>
                            <div className="preflight-list">
                              {items.map((item, index) => (
                                <article key={`${item.asset_id}-${item.template_id}-${status}-${index}`} className="preflight-item">
                                  <strong>{item.asset_filename || selectedAsset?.original_filename || '当前视频'} / {item.title || item.template_name}</strong>
                                  <span>
                                    {preflightStatusLabel(item.status, item.missing_fields)} ·{' '}
                                    {item.output_width && item.output_height
                                      ? `${item.output_width}x${item.output_height}`
                                      : '原始尺寸'} · {item.fit}
                                  </span>
                                  {item.missing_fields.length > 0 && <small>缺少：{item.missing_fields.join('、')}</small>}
                                  {item.warnings.length > 0 && <small>{item.warnings.join('；')}</small>}
                                  {status === 'blocked' && (
                                    <div className="button-row">
                                      <button className="secondary-action" type="button" onClick={() => setStep('params')}>
                                        补本次参数
                                      </button>
                                      <button className="secondary-action" type="button" onClick={() => setStep('templates')}>
                                        换模板
                                      </button>
                                      <button className="secondary-action" type="button" onClick={saveDraft}>
                                        暂存
                                      </button>
                                    </div>
                                  )}
                                </article>
                              ))}
                            </div>
                          </section>
                        );
                      })}
                    </div>
                  )}
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
                  {createdTasks.length > 0 && (
                    <div className="queue-next-actions">
                      <div>
                        <strong>下一步建议</strong>
                        <span>先去队列看失败和进度；任务完成后再进入审核。</span>
                      </div>
                      <div className="button-row">
                        <button className="primary-action" type="button" onClick={onGoToQueue}>
                          去队列与失败
                        </button>
                        <button className="secondary-action" type="button" onClick={onGoToReview}>
                          稍后审核
                        </button>
                      </div>
                    </div>
                  )}
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
                {step !== 'queue' && (
                  <button className="secondary-action" type="button" onClick={saveDraft} disabled={busy}>
                    暂存草稿
                  </button>
                )}
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
                    <button className="secondary-action" type="button" onClick={onGoToQueue}>
                      队列与失败
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

function RuntimeFieldControl({
  field,
  value,
  videoAssets,
  imageAssets,
  musicTracks,
  onChange
}: {
  field: RuntimeField;
  value: RuntimeValue | '';
  videoAssets: AIAsset[];
  imageAssets: AIAsset[];
  musicTracks: MusicTrack[];
  onChange: (value: RuntimeValue | '') => void;
}) {
  if (field.field_type === 'music') {
    return (
      <label className="runtime-field-card">
        <RuntimeFieldLabel field={field} />
        <select
          value={runtimeValueId(value)}
          onChange={(event) => onChange(event.target.value ? Number(event.target.value) : '')}
        >
          <option value="">按模板默认</option>
          {musicTracks.map((track) => (
            <option key={track.id} value={track.id}>
              {track.scope === 'system' ? '系统' : '私有'} · {track.title}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (field.field_type === 'asset') {
    const pool = field.asset_kind === 'image'
      ? imageAssets.filter((asset) => rightsStatusFromTags(asset.tags) === 'licensed')
      : videoAssets;
    const filteredPool = pool.filter((asset) => {
      if (!field.asset_type) return true;
      return asset.asset_type === field.asset_type;
    });
    return (
      <label className="runtime-field-card">
        <RuntimeFieldLabel field={field} />
        <select
          value={runtimeValueId(value)}
          onChange={(event) =>
            onChange(event.target.value ? { asset_id: Number(event.target.value) } : '')
          }
        >
          <option value="">未选择</option>
          {filteredPool.map((asset) => (
            <option key={asset.id} value={asset.id}>
              #{asset.id} {asset.title} · {labelForAIAssetType(asset.asset_type)}
            </option>
          ))}
        </select>
        {filteredPool.length === 0 && (
          <small>
            {field.asset_kind === 'image'
              ? '没有已授权图片素材，请先到素材库上传。'
              : '没有匹配的视频片段，请先到视频片段库补充。'}
          </small>
        )}
      </label>
    );
  }

  return (
    <label className="runtime-field-card">
      <RuntimeFieldLabel field={field} />
      <input
        value={typeof value === 'string' ? value : ''}
        maxLength={field.max_length}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function RuntimeFieldLabel({ field }: { field: RuntimeField }) {
  return (
    <span className="runtime-field-label">
      <strong>{field.label || field.key}</strong>
      <small>
        {field.required ? '必填' : '可选'}
        {field.asset_kind ? ` · ${field.asset_kind}` : ''}
        {field.asset_type ? ` · ${labelForAIAssetType(field.asset_type)}` : ''}
      </small>
    </span>
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

function runtimeFieldsForTemplates(templates: Template[]): RuntimeField[] {
  const map = new Map<string, RuntimeField>();
  templates.forEach((template) => {
    const runtimeFields = template.json_spec.runtime_fields;
    if (!Array.isArray(runtimeFields)) return;
    runtimeFields.forEach((field) => {
      if (!field || typeof field !== 'object' || Array.isArray(field)) return;
      const record = field as Record<string, unknown>;
      const key = typeof record.key === 'string' ? record.key : '';
      if (!key || map.has(key)) return;
      map.set(key, {
        key,
        label: typeof record.label === 'string' ? record.label : key,
        field_type: typeof record.field_type === 'string' ? record.field_type : 'text',
        asset_kind: typeof record.asset_kind === 'string' ? record.asset_kind : undefined,
        asset_type: typeof record.asset_type === 'string' ? record.asset_type : undefined,
        required: typeof record.required === 'boolean' ? record.required : false,
        max_length: typeof record.max_length === 'number' ? record.max_length : undefined
      });
    });
  });
  return Array.from(map.values());
}

function buildAutoNamePrefix(
  productionMode: ProductionMode,
  assetIds: number[],
  templates: Template[],
  assets: Asset[]
): string {
  const firstAsset = assets.find((asset) => asset.id === assetIds[0]);
  const assetPart = firstAsset
    ? cleanName(firstAsset.original_filename.replace(/\.[^.]+$/, '')).slice(0, 22)
    : assetIds.length > 1
      ? `${assetIds.length}-assets`
      : 'batch';
  const templatePart = templates.length === 1
    ? cleanName(templateTitle(templates[0])).slice(0, 20)
    : templates.length > 1
      ? `${templates.length}-templates`
      : 'template';
  const modePart = productionMode === 'many_assets_many_templates'
    ? 'matrix'
    : productionMode === 'one_asset_many_templates'
      ? 'variants'
      : 'batch';
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 12);
  return [stamp, modePart, assetPart, templatePart].filter(Boolean).join('-');
}

function cleanName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'item';
}

function runtimeValueId(value: RuntimeValue | ''): string {
  if (!value) return '';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'object' && 'asset_id' in value) return String(value.asset_id);
  return '';
}

function groupPreflightItems(items: PreflightItem[]) {
  return items.reduce<{
    blocked: PreflightItem[];
    warning: PreflightItem[];
    ready: PreflightItem[];
  }>(
    (result, item) => {
      if (item.status === 'blocked' || item.missing_fields.length > 0) {
        result.blocked.push(item);
      } else if (item.status === 'warning' || item.warnings.length > 0) {
        result.warning.push(item);
      } else {
        result.ready.push(item);
      }
      return result;
    },
    { blocked: [], warning: [], ready: [] }
  );
}

function preflightGroupLabel(status: 'blocked' | 'warning' | 'ready') {
  const labels = {
    blocked: '阻塞项',
    warning: '提醒项',
    ready: '可入队'
  };
  return labels[status];
}

function preflightGroupDescription(status: 'blocked' | 'warning' | 'ready') {
  const descriptions = {
    blocked: '缺少必填字段或素材，不能入队。',
    warning: '可以入队，但审核时要重点检查。',
    ready: '预检通过，可以进入渲染队列。'
  };
  return descriptions[status];
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
