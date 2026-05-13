import { FormEvent, useState } from 'react';
import { api } from '../api/client';
import { templateBadge, templateSummary, templateTitle } from '../api/templateDisplay';
import type { Template } from '../api/types';
import { JsonBlock } from '../components/JsonBlock';

type TemplatesPageProps = {
  templates: Template[];
  onRefresh: () => Promise<void>;
};

const defaultTemplate = {
  type: 'concat',
  creative_goal: {
    title: '竖屏快速钩子',
    audience: '冷启动人群',
    selling_points: ['开头视觉钩子', '真人实拍证明'],
    tone: '直接转化'
  },
  editing: {
    cut_style: 'fixed_interval',
    clip_duration_seconds: 3,
    target_duration_seconds: 9,
    max_clip_count: 3,
    pacing: 'fast',
    keep_original_order: true
  },
  delivery: {
    aspect_ratio: '9:16',
    width: 1080,
    height: 1920,
    fps: 30,
    format: 'mp4',
    fit: 'cover'
  },
  transformations: {
    brightness: 0.03,
    contrast: 1.08,
    saturation: 1.12,
    playback_speed: 1.03,
    volume: 0.95,
    mute_audio: false
  },
  review_notes: '确认改剪变化明显、文案可读，并且素材权利清晰。'
};

export function TemplatesPage({ templates, onRefresh }: TemplatesPageProps) {
  const [name, setName] = useState('vertical-fast-hook');
  const [description, setDescription] = useState('9:16 短视频钩子变体。');
  const [jsonSpec, setJsonSpec] = useState(JSON.stringify(defaultTemplate, null, 2));
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [validation, setValidation] = useState<{
    normalized_spec: Record<string, unknown>;
    warnings: string[];
  } | null>(null);

  const selectedTemplate = templates.find((template) => template.id === selectedId);

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
      await api.updateTemplate(selectedTemplate.id, {
        name,
        description,
        version: selectedTemplate.version + 1,
        json_spec: parsed
      });
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

  function updateField(path: string, value: unknown) {
    const next = parsedSpec();
    const keys = path.split('.');
    let cursor: Record<string, unknown> = next;
    keys.slice(0, -1).forEach((key) => {
      const existing = cursor[key];
      if (!existing || typeof existing !== 'object' || Array.isArray(existing)) {
        cursor[key] = {};
      }
      cursor = cursor[key] as Record<string, unknown>;
    });
    cursor[keys[keys.length - 1]] = value;
    setJsonSpec(JSON.stringify(next, null, 2));
  }

  function applyLastCoverRegions() {
    const raw = localStorage.getItem('flashcutter_last_cover_regions');
    if (!raw) {
      setError('没有可应用的检测结果，请先在素材页检测文字区域。');
      return;
    }
    try {
      updateField('transformations.cover_regions', JSON.parse(raw));
      setError('');
    } catch {
      setError('检测结果格式无效。');
    }
  }

  return (
    <section className="workspace-grid">
      <div className="panel">
        <div className="panel-header">
          <h2>{selectedTemplate ? '编辑模板' : '创建模板'}</h2>
          {selectedTemplate && <button onClick={resetCreateMode}>新建</button>}
        </div>
        <form onSubmit={createTemplate} className="form-stack">
          <div className="template-form-grid">
            <label>
              创意标题
              <input
                value={String(field('creative_goal.title'))}
                onChange={(event) => updateField('creative_goal.title', event.target.value)}
              />
            </label>
            <label>
              目标人群
              <input
                value={String(field('creative_goal.audience'))}
                onChange={(event) => updateField('creative_goal.audience', event.target.value)}
              />
            </label>
            <label>
              片段秒数
              <input
                type="number"
                min="0.5"
                step="0.5"
                value={Number(field('editing.clip_duration_seconds', 3))}
                onChange={(event) =>
                  updateField('editing.clip_duration_seconds', Number(event.target.value))
                }
              />
            </label>
            <label>
              片段数量
              <input
                type="number"
                min="1"
                value={Number(field('editing.max_clip_count', 3))}
                onChange={(event) =>
                  updateField('editing.max_clip_count', Number(event.target.value))
                }
              />
            </label>
            <label>
              输出宽度
              <input
                type="number"
                value={Number(field('delivery.width', 1080))}
                onChange={(event) => updateField('delivery.width', Number(event.target.value))}
              />
            </label>
            <label>
              输出高度
              <input
                type="number"
                value={Number(field('delivery.height', 1920))}
                onChange={(event) => updateField('delivery.height', Number(event.target.value))}
              />
            </label>
            <label>
              适配方式
              <select
                value={String(field('delivery.fit', 'cover'))}
                onChange={(event) => updateField('delivery.fit', event.target.value)}
              >
                <option value="cover">裁切填满</option>
                <option value="contain">完整保留</option>
                <option value="original">原始适配</option>
              </select>
            </label>
            <label>
              播放速度
              <input
                type="number"
                min="0.5"
                max="2"
                step="0.05"
                value={Number(field('transformations.playback_speed', 1))}
                onChange={(event) =>
                  updateField('transformations.playback_speed', Number(event.target.value))
                }
              />
            </label>
          </div>
          <div className="button-row">
            <button type="button" className="secondary-action" onClick={applyLastCoverRegions}>
              应用最近检测的文字遮盖区域
            </button>
          </div>

          <details className="template-section" open>
            <summary>开头钩子卡（intro_card）</summary>
            <div className="template-form-grid">
              <label>
                启用
                <input
                  type="checkbox"
                  checked={Boolean(field('intro_card.enabled', false))}
                  onChange={(event) =>
                    updateField('intro_card.enabled', event.target.checked)
                  }
                />
              </label>
              <label>
                时长（秒）
                <input
                  type="number"
                  min="0.3"
                  max="5"
                  step="0.1"
                  value={Number(field('intro_card.duration_seconds', 1.5))}
                  onChange={(event) =>
                    updateField('intro_card.duration_seconds', Number(event.target.value))
                  }
                />
              </label>
              <label className="form-wide">
                主标题
                <input
                  value={String(field('intro_card.text', ''))}
                  onChange={(event) => updateField('intro_card.text', event.target.value)}
                  placeholder="如：3 秒看懂"
                />
              </label>
              <label className="form-wide">
                副标题
                <input
                  value={String(field('intro_card.subtitle', ''))}
                  onChange={(event) =>
                    updateField('intro_card.subtitle', event.target.value)
                  }
                  placeholder="可选，如：真实记录 · 亲测 30 天"
                />
              </label>
              <label>
                背景色
                <input
                  value={String(field('intro_card.background_color', 'black'))}
                  onChange={(event) =>
                    updateField('intro_card.background_color', event.target.value)
                  }
                />
              </label>
              <label>
                文字色
                <input
                  value={String(field('intro_card.font_color', 'white'))}
                  onChange={(event) =>
                    updateField('intro_card.font_color', event.target.value)
                  }
                />
              </label>
              <label>
                主标题字号
                <input
                  type="number"
                  min="12"
                  max="240"
                  value={Number(field('intro_card.font_size', 72))}
                  onChange={(event) =>
                    updateField('intro_card.font_size', Number(event.target.value))
                  }
                />
              </label>
              <label>
                副标题字号
                <input
                  type="number"
                  min="12"
                  max="200"
                  value={Number(field('intro_card.subtitle_font_size', 40))}
                  onChange={(event) =>
                    updateField('intro_card.subtitle_font_size', Number(event.target.value))
                  }
                />
              </label>
            </div>
          </details>

          <details className="template-section">
            <summary>常驻字幕条（subtitle_bar）</summary>
            <div className="template-form-grid">
              <label>
                启用
                <input
                  type="checkbox"
                  checked={Boolean(field('subtitle_bar.enabled', false))}
                  onChange={(event) =>
                    updateField('subtitle_bar.enabled', event.target.checked)
                  }
                />
              </label>
              <label>
                位置
                <select
                  value={String(field('subtitle_bar.position', 'bottom'))}
                  onChange={(event) =>
                    updateField('subtitle_bar.position', event.target.value)
                  }
                >
                  <option value="bottom">底部</option>
                  <option value="top">顶部</option>
                  <option value="center">居中</option>
                </select>
              </label>
              <label className="form-wide">
                文案
                <input
                  value={String(field('subtitle_bar.text', ''))}
                  onChange={(event) => updateField('subtitle_bar.text', event.target.value)}
                  placeholder="如：真实记录 · 30 天亲测"
                />
              </label>
              <label>
                文字色
                <input
                  value={String(field('subtitle_bar.font_color', 'white'))}
                  onChange={(event) =>
                    updateField('subtitle_bar.font_color', event.target.value)
                  }
                />
              </label>
              <label>
                字号
                <input
                  type="number"
                  min="12"
                  max="160"
                  value={Number(field('subtitle_bar.font_size', 48))}
                  onChange={(event) =>
                    updateField('subtitle_bar.font_size', Number(event.target.value))
                  }
                />
              </label>
              <label>
                条带颜色
                <input
                  value={String(field('subtitle_bar.bar_color', 'black@0.6'))}
                  onChange={(event) =>
                    updateField('subtitle_bar.bar_color', event.target.value)
                  }
                  placeholder="如 black@0.6 或 none"
                />
              </label>
              <label>
                条带高度
                <input
                  type="number"
                  min="20"
                  max="600"
                  value={Number(field('subtitle_bar.bar_height', 140))}
                  onChange={(event) =>
                    updateField('subtitle_bar.bar_height', Number(event.target.value))
                  }
                />
              </label>
            </div>
          </details>

          <details className="template-section">
            <summary>结尾 CTA 卡（outro_card）</summary>
            <div className="template-form-grid">
              <label>
                启用
                <input
                  type="checkbox"
                  checked={Boolean(field('outro_card.enabled', false))}
                  onChange={(event) =>
                    updateField('outro_card.enabled', event.target.checked)
                  }
                />
              </label>
              <label>
                时长（秒）
                <input
                  type="number"
                  min="0.3"
                  max="5"
                  step="0.1"
                  value={Number(field('outro_card.duration_seconds', 1.5))}
                  onChange={(event) =>
                    updateField('outro_card.duration_seconds', Number(event.target.value))
                  }
                />
              </label>
              <label className="form-wide">
                主标题
                <input
                  value={String(field('outro_card.text', ''))}
                  onChange={(event) => updateField('outro_card.text', event.target.value)}
                  placeholder="如：点击购买"
                />
              </label>
              <label className="form-wide">
                副标题
                <input
                  value={String(field('outro_card.subtitle', ''))}
                  onChange={(event) =>
                    updateField('outro_card.subtitle', event.target.value)
                  }
                  placeholder="可选，如：限时优惠 立即领取"
                />
              </label>
              <label>
                背景色
                <input
                  value={String(field('outro_card.background_color', 'black'))}
                  onChange={(event) =>
                    updateField('outro_card.background_color', event.target.value)
                  }
                />
              </label>
              <label>
                文字色
                <input
                  value={String(field('outro_card.font_color', 'white'))}
                  onChange={(event) =>
                    updateField('outro_card.font_color', event.target.value)
                  }
                />
              </label>
              <label>
                主标题字号
                <input
                  type="number"
                  min="12"
                  max="240"
                  value={Number(field('outro_card.font_size', 72))}
                  onChange={(event) =>
                    updateField('outro_card.font_size', Number(event.target.value))
                  }
                />
              </label>
              <label>
                副标题字号
                <input
                  type="number"
                  min="12"
                  max="200"
                  value={Number(field('outro_card.subtitle_font_size', 40))}
                  onChange={(event) =>
                    updateField('outro_card.subtitle_font_size', Number(event.target.value))
                  }
                />
              </label>
            </div>
          </details>

          <details className="template-section">
            <summary>画面安全区（safe area）</summary>
            <div className="template-form-grid">
              <label>
                顶部安全区（像素）
                <input
                  type="number"
                  min="0"
                  max="2000"
                  value={Number(field('delivery.safe_area_top', 0))}
                  onChange={(event) =>
                    updateField('delivery.safe_area_top', Number(event.target.value))
                  }
                />
              </label>
              <label>
                底部安全区（像素）
                <input
                  type="number"
                  min="0"
                  max="2000"
                  value={Number(field('delivery.safe_area_bottom', 0))}
                  onChange={(event) =>
                    updateField('delivery.safe_area_bottom', Number(event.target.value))
                  }
                />
              </label>
            </div>
            <p className="form-hint">
              启用字幕条时会自动按条带高度预留安全区。若需画面整体内缩，可手动设置。
            </p>
          </details>

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
            运营模板 JSON
            <textarea
              value={jsonSpec}
              onChange={(event) => setJsonSpec(event.target.value)}
              rows={18}
            />
          </label>
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
                保存修改
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
                <div className="button-row">
                  <button onClick={() => editTemplate(template)}>编辑</button>
                </div>
              </div>
              <JsonBlock value={template.json_spec} />
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
