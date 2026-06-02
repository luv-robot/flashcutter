import { FormEvent, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type { CreativeReference } from '../api/types';

const componentTypes = [
  { value: '', label: '自动判断' },
  { value: 'layout_reference', label: '整版布局' },
  { value: 'poster_layout', label: '海报版式' },
  { value: 'product_card', label: '商品卡片' },
  { value: 'price_tag', label: '价格标签' },
  { value: 'coupon_strip', label: '优惠券条' },
  { value: 'headline_block', label: '标题块' },
  { value: 'cta_panel', label: '行动按钮区' }
];

const rightsLabels: Record<string, string> = {
  reference_only: '仅参考',
  needs_review: '待确认',
  licensed: '已授权',
  owned: '自有',
  public_domain: '公有领域',
  cc_by: 'CC BY'
};

export function CreativeReferencesPage() {
  const [references, setReferences] = useState<CreativeReference[]>([]);
  const [url, setUrl] = useState('');
  const [componentType, setComponentType] = useState('');
  const [industry, setIndustry] = useState('');
  const [tags, setTags] = useState('电商,海报');
  const [notes, setNotes] = useState('外部素材站参考，先做版式拆解，未确认授权前不作为生产素材。');
  const [filter, setFilter] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const visibleReferences = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return references;
    return references.filter((item) => {
      const haystack = [
        item.title,
        item.source_site,
        item.component_type,
        item.industry,
        item.rights_status,
        item.style_tags.join(' '),
        item.notes
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [references, filter]);

  async function refresh() {
    setReferences(await api.listCreativeReferences());
  }

  useEffect(() => {
    void refresh().catch((err) =>
      setMessage(err instanceof Error ? err.message : '加载组件参考失败')
    );
  }, []);

  async function submitImport(event: FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    setMessage('正在导入参考页...');
    try {
      const styleTags = tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean);
      const reference = await api.importCreativeReference({
        url: url.trim(),
        component_type: componentType || undefined,
        industry: industry.trim() || undefined,
        style_tags: styleTags,
        notes: notes.trim() || undefined
      });
      setUrl('');
      await refresh();
      setMessage(
        reference.image_url
          ? '已导入参考。系统只记录远程预览图 URL，确认授权前不会下载或生产使用。'
          : '已记录参考 URL。页面没有提供可读图片元信息，后续可人工补充标题和组件拆解。'
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '导入失败，请稍后重试');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workspace-grid reference-workspace">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2>组件参考导入</h2>
            <p>从广告、电商海报等页面沉淀可复用结构。默认仅做参考和拆解。</p>
          </div>
        </div>
        <form className="form-stack" onSubmit={submitImport}>
          <label>
            素材页 URL
            <input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://huaban.com/pins/7094417768"
            />
          </label>
          <label>
            组件类型
            <select
              value={componentType}
              onChange={(event) => setComponentType(event.target.value)}
            >
              {componentTypes.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            行业
            <input
              value={industry}
              onChange={(event) => setIndustry(event.target.value)}
              placeholder="beauty / food / electronics"
            />
          </label>
          <label>
            标签
            <input value={tags} onChange={(event) => setTags(event.target.value)} />
          </label>
          <label>
            操作备注
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>
          <button type="submit" disabled={busy || !url.trim()}>
            {busy ? '导入中...' : '导入为参考组件'}
          </button>
        </form>
        {message && <div className="notice reference-notice">{message}</div>}
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <h2>组件参考库</h2>
            <p>运营先看结构：标题区、商品区、利益点、CTA，再转成可复用模板组件。</p>
          </div>
          <button type="button" onClick={() => void refresh()}>
            刷新
          </button>
        </div>
        <input
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="按标题、类型、行业、标签搜索"
        />
        <div className="reference-grid">
          {visibleReferences.map((item) => (
            <article key={item.id} className="reference-card">
              {item.image_url ? (
                <img src={item.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
              ) : (
                <div className="reference-placeholder">无预览图</div>
              )}
              <div className="reference-card-body">
                <div className="reference-card-title">
                  <h3>{item.title}</h3>
                  <span className={`status status-${item.rights_status}`}>
                    {rightsLabels[item.rights_status] || item.rights_status}
                  </span>
                </div>
                <p>
                  {componentLabel(item.component_type)} · {item.industry || '未分行业'} ·{' '}
                  {item.source_site || '外部来源'}
                </p>
                <div className="tag-row">
                  {item.style_tags.map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                  {item.style_tags.length === 0 && <span>待打标</span>}
                </div>
                {item.notes && <small>{item.notes}</small>}
                <a href={item.source_url} target="_blank" rel="noreferrer">
                  打开原始页面
                </a>
              </div>
            </article>
          ))}
          {visibleReferences.length === 0 && (
            <div className="notice">还没有参考组件。先导入一个素材站页面 URL。</div>
          )}
        </div>
      </div>
    </section>
  );
}

function componentLabel(value: string): string {
  return componentTypes.find((item) => item.value === value)?.label || value;
}
