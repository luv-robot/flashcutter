import { FormEvent, useEffect, useState } from 'react';
import { api } from '../api/client';
import { templateBadge, templateSummary, templateTitle } from '../api/templateDisplay';
import type { MusicTrack, Template } from '../api/types';
import { JsonBlock } from '../components/JsonBlock';

type TemplatesPageProps = {
  templates: Template[];
  onRefresh: () => Promise<void>;
};

type TextOverlayLayer = {
  text: string;
  x: number;
  y: number;
  font_size: number;
  font_color: string;
  box_color: string | null;
  box_padding: number;
};

const defaultTemplate = {
  schema_version: 2,
  type: 'variant_recipe',
  recipe_id: 'custom.vertical_fast_hook',
  name: 'vertical-fast-hook',
  blueprint: {
    blueprint_id: 'custom_hook_blueprint_v1',
    name: '竖屏快速钩子',
    creative_goal: {
      title: '竖屏快速钩子',
      audience: '冷启动人群',
      selling_points: ['开头视觉钩子', '真人实拍证明'],
      tone: '直接转化'
    },
    production_contract: {
      use_case: '用于上传前已完成授权确认的真人实拍素材第一轮试生产广告变体。',
      operator_notes: '适合素材开头有明确人物、产品或动作钩子的短视频；素材授权在进入系统前完成。',
      review_checklist: [
        '前三秒钩子清晰。',
        '主体裁切没有遮挡人物或产品。',
        '叠加文字在手机预览中可读。'
      ]
    },
    editing: {
      cut_style: 'fixed_interval',
      clip_duration_seconds: 3,
      target_duration_seconds: 9,
      max_clip_count: 3,
      pacing: 'fast',
      keep_original_order: true
    },
    slots: [{ slot: 'hook', role: 'source_segment' }]
  },
  render_preset: {
    preset_id: 'custom_vertical_9_16',
    name: '9:16 竖屏',
    delivery: {
      aspect_ratio: '9:16',
      width: 1080,
      height: 1920,
      fps: 30,
      format: 'mp4',
      fit: 'cover'
    }
  },
  style_pack: {
    style_pack_id: 'custom_clean_ad',
    name: '清爽广告',
    transformations: {
      orientation: 'normal',
      visual_style: 'clean_ad',
      finishing_style: 'sharpen',
      motion_style: 'none',
      transition_style: 'hard_cut',
      texture_style: 'none',
      brightness: 0.03,
      contrast: 1.08,
      saturation: 1.12,
      playback_speed: 1.03,
      volume: 0.95,
      mute_audio: false
    }
  },
  review_notes: '确认改剪变化明显、文案可读，并且符合上传前已授权素材的试投放用途。'
};

const outputPresetOptions = [
  {
    id: 'vertical_9_16_cover',
    label: '竖版 9:16 填满画面',
    aspect_ratio: '9:16',
    width: 1080,
    height: 1920,
    fps: 30,
    fit: 'cover'
  },
  {
    id: 'vertical_9_16_contain',
    label: '竖版 9:16 保留完整画面',
    aspect_ratio: '9:16',
    width: 1080,
    height: 1920,
    fps: 30,
    fit: 'contain'
  },
  {
    id: 'square_1_1_contain',
    label: '方版 1:1',
    aspect_ratio: '1:1',
    width: 1080,
    height: 1080,
    fps: 30,
    fit: 'contain'
  },
  {
    id: 'horizontal_16_9_cover',
    label: '横版 16:9',
    aspect_ratio: '16:9',
    width: 1920,
    height: 1080,
    fps: 30,
    fit: 'cover'
  },
  {
    id: 'source_original',
    label: '保持原尺寸',
    aspect_ratio: 'source',
    width: 1280,
    height: 720,
    fps: 30,
    fit: 'original'
  }
];

export function TemplatesPage({ templates, onRefresh }: TemplatesPageProps) {
  const [name, setName] = useState('vertical-fast-hook');
  const [description, setDescription] = useState('9:16 短视频钩子变体。');
  const [jsonSpec, setJsonSpec] = useState(JSON.stringify(defaultTemplate, null, 2));
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showAdvancedJson, setShowAdvancedJson] = useState(false);
  const [musicTracks, setMusicTracks] = useState<MusicTrack[]>([]);
  const [validation, setValidation] = useState<{
    normalized_spec: Record<string, unknown>;
    warnings: string[];
  } | null>(null);

  const selectedTemplate = templates.find((template) => template.id === selectedId);

  useEffect(() => {
    void api.listMusic()
      .then(setMusicTracks)
      .catch(() => setMusicTracks([]));
  }, []);

  async function createTemplate(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const parsed = JSON.parse(jsonSpec) as Record<string, unknown>;
      await api.createTemplate({
        name,
        description,
        version: 1,
        json_spec: parsed
      });
      await onRefresh();
      setValidation(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建模板失败');
    }
  }

  function editTemplate(template: Template) {
    setSelectedId(template.id);
    setName(template.name);
    setDescription(template.description ?? '');
    setJsonSpec(JSON.stringify(template.json_spec, null, 2));
    setError('');
    setValidation(null);
  }

  async function validateJson() {
    setError('');
    try {
      const parsed = JSON.parse(jsonSpec) as Record<string, unknown>;
      const result = await api.validateTemplate(parsed);
      setValidation(result);
    } catch (err) {
      setValidation(null);
      setError(err instanceof Error ? err.message : '模板校验失败');
    }
  }

  async function saveTemplate() {
    if (!selectedTemplate) return;
    setError('');
    try {
      const parsed = JSON.parse(jsonSpec) as Record<string, unknown>;
      if (selectedTemplate.is_builtin) {
        await api.createTemplate({
          name: uniqueCopyName(name),
          description,
          version: 1,
          json_spec: parsed,
          is_builtin: false
        });
      } else {
        await api.updateTemplate(selectedTemplate.id, {
          name,
          description,
          version: selectedTemplate.version + 1,
          json_spec: parsed
        });
      }
      await onRefresh();
      setValidation(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存模板失败');
    }
  }

  function resetCreateMode() {
    setSelectedId(null);
    setName('vertical-fast-hook');
    setDescription('9:16 短视频钩子变体。');
    setJsonSpec(JSON.stringify(defaultTemplate, null, 2));
    setError('');
    setValidation(null);
  }

  function parsedSpec(): Record<string, unknown> {
    try {
      return JSON.parse(jsonSpec) as Record<string, unknown>;
    } catch {
      return {};
    }
  }

  function field(path: string, fallback: unknown = '') {
    const value = path.split('.').reduce<unknown>((current, key) => {
      return current && typeof current === 'object'
        ? (current as Record<string, unknown>)[key]
        : undefined;
    }, parsedSpec());
    return value ?? fallback;
  }

  function textField(path: string, fallback = '') {
    const value = field(path, fallback);
    return typeof value === 'string' ? value : fallback;
  }

  function numberField(path: string, fallback: number) {
    const value = field(path, fallback);
    return typeof value === 'number' ? value : fallback;
  }

  function boolField(path: string, fallback = false) {
    const value = field(path, fallback);
    return typeof value === 'boolean' ? value : fallback;
  }

  function listField(path: string) {
    const value = field(path, []);
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
  }

  function textOverlayLayers(): TextOverlayLayer[] {
    const value = field('style_pack.transformations.text_overlays', []);
    if (!Array.isArray(value)) return [];
    return value
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
      .map((item) => ({
        text: typeof item.text === 'string' ? item.text : '',
        x: typeof item.x === 'number' ? item.x : 72,
        y: typeof item.y === 'number' ? item.y : 220,
        font_size: typeof item.font_size === 'number' ? item.font_size : 54,
        font_color: typeof item.font_color === 'string' ? item.font_color : 'white',
        box_color: typeof item.box_color === 'string' ? item.box_color : 'black@0.62',
        box_padding: typeof item.box_padding === 'number' ? item.box_padding : 18
      }));
  }

  function updateTextOverlay(index: number, patch: Partial<TextOverlayLayer>) {
    const next = textOverlayLayers();
    next[index] = { ...next[index], ...patch };
    updateField('style_pack.transformations.text_overlays', next);
  }

  function addTextOverlay() {
    updateField('style_pack.transformations.text_overlays', [
      ...textOverlayLayers(),
      {
        text: '新文字层',
        x: 72,
        y: 220,
        font_size: 54,
        font_color: 'white',
        box_color: 'black@0.62',
        box_padding: 18
      }
    ]);
  }

  function removeTextOverlay(index: number) {
    updateField(
      'style_pack.transformations.text_overlays',
      textOverlayLayers().filter((_, layerIndex) => layerIndex !== index)
    );
  }

  function updateListField(path: string, value: string) {
    updateField(
      path,
      value
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean)
    );
  }

  function updateField(path: string, value: unknown) {
    updateFields([[path, value]]);
  }

  function updateFields(patches: Array<[string, unknown]>) {
    const next = parsedSpec();
    patches.forEach(([path, value]) => {
      const keys = path.split('.');
      let cursor: Record<string, unknown> | unknown[] = next;
      keys.slice(0, -1).forEach((key, indexInPath) => {
        const nextKey = keys[indexInPath + 1];
        const shouldBeArray = isArrayIndex(nextKey);
        const index = isArrayIndex(key) ? Number(key) : key;
        const container = cursor as Record<string | number, unknown>;
        const existing = container[index];
        if (!existing || typeof existing !== 'object') {
          container[index] = shouldBeArray ? [] : {};
        }
        cursor = container[index] as Record<string, unknown> | unknown[];
      });
      const lastKey = keys[keys.length - 1];
      const lastIndex = isArrayIndex(lastKey) ? Number(lastKey) : lastKey;
      (cursor as Record<string | number, unknown>)[lastIndex] = value;
    });
    setJsonSpec(JSON.stringify(next, null, 2));
  }

  function applyLastCoverRegions() {
    const raw = localStorage.getItem('flashcutter_last_cover_regions');
    if (!raw) {
      setError('没有可应用的检测结果，请先在素材页检测文字区域。');
      return;
    }
    try {
      updateField('style_pack.transformations.cover_regions', JSON.parse(raw));
      setError('');
    } catch {
      setError('检测结果格式无效。');
    }
  }

  function updateMusicTrack(trackId: string) {
    if (!trackId) {
      updateField('music.track_id', undefined);
      return;
    }
    updateFields([
      ['music.mode', 'replace'],
      ['music.track_id', Number(trackId)],
      ...(field('music.volume', null) === null ? [['music.volume', 1] as [string, unknown]] : []),
      ...(field('music.loop', null) === null ? [['music.loop', true] as [string, unknown]] : [])
    ]);
  }

  function currentOutputPresetId() {
    const delivery = {
      aspect_ratio: textField('render_preset.delivery.aspect_ratio', '9:16'),
      width: numberField('render_preset.delivery.width', 1080),
      height: numberField('render_preset.delivery.height', 1920),
      fps: numberField('render_preset.delivery.fps', 30),
      fit: textField('render_preset.delivery.fit', 'cover')
    };
    return outputPresetOptions.find((preset) =>
      preset.aspect_ratio === delivery.aspect_ratio &&
      preset.width === delivery.width &&
      preset.height === delivery.height &&
      preset.fps === delivery.fps &&
      preset.fit === delivery.fit
    )?.id ?? 'custom';
  }

  function applyOutputPreset(presetId: string) {
    const preset = outputPresetOptions.find((item) => item.id === presetId);
    if (!preset) return;
    updateFields([
      ['render_preset.delivery.aspect_ratio', preset.aspect_ratio],
      ['render_preset.delivery.width', preset.width],
      ['render_preset.delivery.height', preset.height],
      ['render_preset.delivery.fps', preset.fps],
      ['render_preset.delivery.fit', preset.fit]
    ]);
  }

  return (
    <section className="workspace-grid">
      <div className="panel">
        <div className="panel-header">
          <h2>{selectedTemplate ? '编辑模板' : '创建模板'}</h2>
          {selectedTemplate && <button onClick={resetCreateMode}>新建</button>}
        </div>
        {selectedTemplate?.is_builtin && (
          <p className="notice">
            内置试生产模板受保护，保存时会创建一份自定义模板。
          </p>
        )}
        <form onSubmit={createTemplate} className="form-stack">
          <div className="template-form-grid">
            <label>
              模板名称
              <input value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label>
              描述
              <input
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
            <label>
              创意标题
              <input
                value={textField('blueprint.creative_goal.title')}
                onChange={(event) => updateField('blueprint.creative_goal.title', event.target.value)}
              />
            </label>
            <label>
              目标人群
              <input
                value={textField('blueprint.creative_goal.audience')}
                onChange={(event) => updateField('blueprint.creative_goal.audience', event.target.value)}
              />
            </label>
            <label>
              语气
              <input
                value={textField('blueprint.creative_goal.tone')}
                onChange={(event) => updateField('blueprint.creative_goal.tone', event.target.value)}
              />
            </label>
            <label>
              输出规格
              <select
                value={currentOutputPresetId()}
                onChange={(event) => applyOutputPreset(event.target.value)}
              >
                <option value="custom">自定义：{deliverySummary(parsedSpec())}</option>
                {outputPresetOptions.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.label} · {preset.width}x{preset.height} · {preset.fps}fps · {fitLabel(preset.fit)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              片段秒数
              <input
                type="number"
                min="0.5"
                step="0.5"
                value={numberField('blueprint.editing.clip_duration_seconds', 3)}
                onChange={(event) =>
                  updateField('blueprint.editing.clip_duration_seconds', Number(event.target.value))
                }
              />
            </label>
            <label>
              片段数量
              <input
                type="number"
                min="1"
                value={numberField('blueprint.editing.max_clip_count', 3)}
                onChange={(event) =>
                  updateField('blueprint.editing.max_clip_count', Number(event.target.value))
                }
              />
            </label>
            <label>
              目标时长
              <input
                type="number"
                min="1"
                step="0.5"
                value={numberField('blueprint.editing.target_duration_seconds', 9)}
                onChange={(event) =>
                  updateField('blueprint.editing.target_duration_seconds', Number(event.target.value))
                }
              />
            </label>
            <label>
              画面方向
              <select
                value={textField('style_pack.transformations.orientation', 'normal')}
                onChange={(event) =>
                  updateField('style_pack.transformations.orientation', event.target.value)
                }
              >
                <option value="normal">正常方向</option>
                <option value="mirror_horizontal">左右镜像</option>
              </select>
            </label>
            <label>
              画面风格
              <select
                value={textField('style_pack.transformations.visual_style', 'natural')}
                onChange={(event) =>
                  updateField('style_pack.transformations.visual_style', event.target.value)
                }
              >
                <option value="natural">自然原片</option>
                <option value="clean_ad">清爽广告</option>
                <option value="warm_lifestyle">暖调生活方式</option>
                <option value="cool_tech">冷调科技感</option>
                <option value="punchy_social">高冲击社媒感</option>
                <option value="soft_beauty">柔和美颜感</option>
              </select>
            </label>
            <label>
              质感处理
              <select
                value={textField('style_pack.transformations.finishing_style', 'none')}
                onChange={(event) =>
                  updateField('style_pack.transformations.finishing_style', event.target.value)
                }
              >
                <option value="none">不额外处理</option>
                <option value="sharpen">轻锐化</option>
                <option value="soften">轻柔化</option>
                <option value="film_grain">轻颗粒</option>
                <option value="vignette">暗角聚焦</option>
              </select>
            </label>
            <label>
              镜头运动
              <select
                value={textField('style_pack.transformations.motion_style', 'none')}
                onChange={(event) =>
                  updateField('style_pack.transformations.motion_style', event.target.value)
                }
              >
                <option value="none">无运动</option>
                <option value="slow_push_in">轻推近</option>
                <option value="slow_pan">缓慢平移</option>
                <option value="light_rotate">轻微旋转</option>
                <option value="social_pulse">社媒快节奏晃动</option>
              </select>
            </label>
            <label>
              转场节奏
              <select
                value={textField('style_pack.transformations.transition_style', 'hard_cut')}
                onChange={(event) =>
                  updateField('style_pack.transformations.transition_style', event.target.value)
                }
              >
                <option value="hard_cut">硬切</option>
                <option value="flash_white">闪白</option>
                <option value="flash_black">闪黑</option>
                <option value="soft_fade">轻淡入</option>
              </select>
            </label>
            <label>
              可见纹理层
              <select
                value={textField('style_pack.transformations.texture_style', 'none')}
                onChange={(event) =>
                  updateField('style_pack.transformations.texture_style', event.target.value)
                }
              >
                <option value="none">无纹理</option>
                <option value="warm_light_leak">暖色光影</option>
                <option value="cool_light_leak">冷色光影</option>
                <option value="subtle_grid">轻网格</option>
              </select>
            </label>
            <label>
              播放速度
              <input
                type="number"
                min="0.5"
                max="2"
                step="0.05"
                value={numberField('style_pack.transformations.playback_speed', 1)}
                onChange={(event) =>
                  updateField('style_pack.transformations.playback_speed', Number(event.target.value))
                }
              />
            </label>
            <label>
              音量
              <input
                type="number"
                min="0"
                max="3"
                step="0.05"
                value={numberField('style_pack.transformations.volume', 1)}
                onChange={(event) => updateField('style_pack.transformations.volume', Number(event.target.value))}
              />
            </label>
            <label>
              亮度
              <input
                type="number"
                min="-1"
                max="1"
                step="0.01"
                value={numberField('style_pack.transformations.brightness', 0)}
                onChange={(event) =>
                  updateField('style_pack.transformations.brightness', Number(event.target.value))
                }
              />
            </label>
            <label>
              对比度
              <input
                type="number"
                min="0"
                max="3"
                step="0.01"
                value={numberField('style_pack.transformations.contrast', 1)}
                onChange={(event) =>
                  updateField('style_pack.transformations.contrast', Number(event.target.value))
                }
              />
            </label>
            <label>
              饱和度
              <input
                type="number"
                min="0"
                max="3"
                step="0.01"
                value={numberField('style_pack.transformations.saturation', 1)}
                onChange={(event) =>
                  updateField('style_pack.transformations.saturation', Number(event.target.value))
                }
              />
            </label>
            <label>
              配乐
              <select
                value={String(numberField('music.track_id', 0) || '')}
                onChange={(event) => updateMusicTrack(event.target.value)}
              >
                <option value="">不替换原声</option>
                {musicTracks.map((track) => (
                  <option key={track.id} value={track.id}>
                    {track.scope === 'system' ? '系统' : '私有'} · {track.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              配乐音量
              <input
                type="number"
                min="0"
                max="3"
                step="0.05"
                value={numberField('music.volume', 1)}
                onChange={(event) => {
                  updateField('music.mode', 'replace');
                  updateField('music.volume', Number(event.target.value));
                }}
              />
            </label>
            <label className="checkbox-row form-checkbox">
              <input
                type="checkbox"
                checked={boolField('style_pack.transformations.mute_audio')}
                onChange={(event) => updateField('style_pack.transformations.mute_audio', event.target.checked)}
              />
              <span>
                <strong>静音输出</strong>
                <small>用于 sound-off 字幕变体。</small>
              </span>
            </label>
            <label className="checkbox-row form-checkbox">
              <input
                type="checkbox"
                checked={boolField('music.loop', true)}
                onChange={(event) => {
                  updateField('music.mode', 'replace');
                  updateField('music.loop', event.target.checked);
                }}
              />
              <span>
                <strong>循环配乐</strong>
                <small>配乐短于成片时循环，最终按视频时长截断。</small>
              </span>
            </label>
            <div className="form-note">
              素材授权默认在上传前由投放公司完成，本系统不做权利真实性判断。
            </div>
          </div>
          <label>
            卖点，每行一个
            <textarea
              value={listField('blueprint.creative_goal.selling_points').join('\n')}
              onChange={(event) => updateListField('blueprint.creative_goal.selling_points', event.target.value)}
              rows={3}
            />
          </label>
          <label>
            适用场景
            <textarea
              value={textField('blueprint.production_contract.use_case')}
              onChange={(event) => updateField('blueprint.production_contract.use_case', event.target.value)}
              rows={3}
            />
          </label>
          <label>
            操作说明
            <textarea
              value={textField('blueprint.production_contract.operator_notes')}
              onChange={(event) =>
                updateField('blueprint.production_contract.operator_notes', event.target.value)
              }
              rows={3}
            />
          </label>
          <label>
            审核清单，每行一个
            <textarea
              value={listField('blueprint.production_contract.review_checklist').join('\n')}
              onChange={(event) =>
                updateListField('blueprint.production_contract.review_checklist', event.target.value)
              }
              rows={4}
            />
          </label>
          <div className="text-layer-editor">
            <div className="panel-header compact">
              <div>
                <h3>画面叠字</h3>
                <p>渲染到视频画面上的文字层；不添加则不改变画面文字。</p>
              </div>
              <button type="button" className="secondary-action" onClick={addTextOverlay}>
                添加文字层
              </button>
            </div>
            {textOverlayLayers().length === 0 ? (
              <p className="empty-state">暂无画面叠字。</p>
            ) : (
              <div className="text-layer-list">
                {textOverlayLayers().map((layer, index) => (
                  <article key={index} className="text-layer-row">
                    <label className="text-layer-copy">
                      文案
                      <input
                        value={layer.text}
                        onChange={(event) =>
                          updateTextOverlay(index, { text: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      X
                      <input
                        type="number"
                        min="0"
                        value={layer.x}
                        onChange={(event) =>
                          updateTextOverlay(index, { x: Number(event.target.value) })
                        }
                      />
                    </label>
                    <label>
                      Y
                      <input
                        type="number"
                        min="0"
                        value={layer.y}
                        onChange={(event) =>
                          updateTextOverlay(index, { y: Number(event.target.value) })
                        }
                      />
                    </label>
                    <label>
                      字号
                      <input
                        type="number"
                        min="12"
                        max="180"
                        value={layer.font_size}
                        onChange={(event) =>
                          updateTextOverlay(index, { font_size: Number(event.target.value) })
                        }
                      />
                    </label>
                    <label>
                      字色
                      <input
                        value={layer.font_color}
                        onChange={(event) =>
                          updateTextOverlay(index, { font_color: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      背景
                      <input
                        value={layer.box_color ?? ''}
                        placeholder="留空则无背景框"
                        onChange={(event) =>
                          updateTextOverlay(index, {
                            box_color: event.target.value.trim() || null
                          })
                        }
                      />
                    </label>
                    <label>
                      边距
                      <input
                        type="number"
                        min="0"
                        max="80"
                        value={layer.box_padding}
                        onChange={(event) =>
                          updateTextOverlay(index, { box_padding: Number(event.target.value) })
                        }
                      />
                    </label>
                    <button
                      type="button"
                      className="secondary-action danger-action"
                      onClick={() => removeTextOverlay(index)}
                    >
                      删除
                    </button>
                  </article>
                ))}
              </div>
            )}
          </div>
          <label>
            审核重点
            <textarea
              value={textField('review_notes')}
              onChange={(event) => updateField('review_notes', event.target.value)}
              rows={3}
            />
          </label>
          <div className="button-row">
            <button type="button" className="secondary-action" onClick={applyLastCoverRegions}>
              应用最近检测的文字遮盖区域
            </button>
            <button
              type="button"
              className="secondary-action"
              onClick={() => setShowAdvancedJson((current) => !current)}
            >
              {showAdvancedJson ? '收起高级 JSON' : '展开高级 JSON'}
            </button>
          </div>
          {showAdvancedJson && (
            <label>
              高级 JSON
              <textarea
                value={jsonSpec}
                onChange={(event) => setJsonSpec(event.target.value)}
                rows={18}
              />
            </label>
          )}
          {error && <p className="error">{error}</p>}
          {validation && (
            <div className="result-box">
              <h3>校验结果</h3>
              {validation.warnings.length ? (
                <ul className="compact-list">
                  {validation.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : (
                <p>无警告。</p>
              )}
              <JsonBlock value={validation.normalized_spec} />
            </div>
          )}
          <div className="button-row">
            <button type="button" onClick={validateJson}>
              校验
            </button>
            {selectedTemplate ? (
              <button type="button" onClick={saveTemplate}>
                {selectedTemplate.is_builtin ? '另存为自定义模板' : '保存修改'}
              </button>
            ) : (
              <button type="submit">创建模板</button>
            )}
          </div>
        </form>
      </div>
      <div className="panel wide">
        <div className="panel-header">
          <h2>模板列表</h2>
          <button onClick={onRefresh}>刷新</button>
        </div>
        <div className="template-list">
          {templates.map((template) => (
            <article key={template.id} className="template-item">
              <div>
                <h3>{templateTitle(template)}</h3>
                <p>
                  {templateBadge(template)} · {templateSummary(template)}
                </p>
                <div className="template-summary-grid">
                  <TemplateSummaryCell
                    label="需要字段"
                    value={runtimeFieldSummary(template)}
                  />
                  <TemplateSummaryCell
                    label="执行动作"
                    value={operationSummary(template)}
                  />
                  <TemplateSummaryCell
                    label="输出规格"
                    value={deliverySummary(template.json_spec)}
                  />
                  <TemplateSummaryCell
                    label="审核重点"
                    value={reviewChecklistSummary(template)}
                  />
                </div>
                <div className="button-row">
                  <button onClick={() => editTemplate(template)}>编辑</button>
                </div>
              </div>
              <details className="template-json-details">
                <summary>高级 JSON</summary>
                <JsonBlock value={template.json_spec} />
              </details>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function TemplateSummaryCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function isArrayIndex(value: string): boolean {
  return /^\d+$/.test(value);
}

function uniqueCopyName(value: string): string {
  const suffix = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14);
  return `${value || 'template'}-copy-${suffix}`;
}

function runtimeFieldSummary(template: Template): string {
  const fields = template.json_spec.runtime_fields;
  if (!Array.isArray(fields) || fields.length === 0) {
    return '无额外字段';
  }
  const labels = fields
    .filter((field): field is Record<string, unknown> => Boolean(field) && typeof field === 'object')
    .map((field) => {
      const label = typeof field.label === 'string' ? field.label : field.key;
      const required = field.required === true ? '必填' : '可选';
      return `${label}(${required})`;
    });
  return labels.slice(0, 4).join('、') + (labels.length > 4 ? ` 等 ${labels.length} 项` : '');
}

function operationSummary(template: Template): string {
  const spec = template.json_spec;
  const blueprint = record(spec.blueprint);
  const editing = record(blueprint.editing);
  const stylePack = record(spec.style_pack);
  const transformations = record(stylePack.transformations);
  const pieces = [
    textValue(editing.cut_style) || '剪辑',
    textValue(transformations.transition_style),
    textValue(transformations.visual_style),
    textValue(transformations.motion_style),
    Number.isFinite(transformations.playback_speed) ? `${transformations.playback_speed}x` : ''
  ].filter(Boolean);
  return pieces.join(' · ') || '按模板方法处理';
}

function deliverySummary(spec: Record<string, unknown>): string {
  const renderPreset = record(spec.render_preset);
  const delivery = record(renderPreset.delivery);
  const width = typeof delivery.width === 'number' ? delivery.width : null;
  const height = typeof delivery.height === 'number' ? delivery.height : null;
  const fps = typeof delivery.fps === 'number' ? delivery.fps : null;
  const aspectRatio = textValue(delivery.aspect_ratio) || 'source';
  const fit = fitLabel(textValue(delivery.fit) || 'original');
  return [
    aspectRatio,
    width && height ? `${width}x${height}` : '源尺寸',
    fps ? `${fps}fps` : '',
    fit
  ].filter(Boolean).join(' · ');
}

function reviewChecklistSummary(template: Template): string {
  const blueprint = record(template.json_spec.blueprint);
  const contract = record(blueprint.production_contract);
  const checklist = contract.review_checklist;
  if (!Array.isArray(checklist) || checklist.length === 0) {
    return textValue(template.json_spec.review_notes) || '按审核说明检查';
  }
  const labels = checklist.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
  return labels.slice(0, 2).join('；') + (labels.length > 2 ? ` 等 ${labels.length} 项` : '');
}

function fitLabel(value: string) {
  const labels: Record<string, string> = {
    cover: '裁切填满',
    contain: '完整保留',
    original: '原始适配'
  };
  return labels[value] ?? value;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function textValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}
