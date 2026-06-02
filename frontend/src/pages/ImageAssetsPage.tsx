import { FormEvent, useEffect, useMemo, useState } from 'react';
import { aiAssetFileUrl, api } from '../api/client';
import {
  formatAssetSize,
  imageAssetTypes,
  labelForAIAssetType,
  labelForRightsStatus,
  rightsStatusFromTags,
  rightsStatusOptions,
  rightsTag
} from '../api/assetDisplay';
import type { AIAsset } from '../api/types';

export function ImageAssetsPage() {
  const [assets, setAssets] = useState<AIAsset[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [assetType, setAssetType] = useState('frame');
  const [rightsStatus, setRightsStatus] = useState('licensed');
  const [notes, setNotes] = useState('');
  const [filterType, setFilterType] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const filteredAssets = useMemo(
    () => assets.filter((asset) => !filterType || asset.asset_type === filterType),
    [assets, filterType]
  );
  const usableCount = assets.filter(
    (asset) => rightsStatusFromTags(asset.tags) === 'licensed'
  ).length;

  async function refreshImages() {
    setError('');
    setAssets(await api.listAIAssets({ asset_kind: 'image' }));
  }

  useEffect(() => {
    void refreshImages().catch((err) =>
      setError(err instanceof Error ? err.message : '加载图片素材失败')
    );
  }, []);

  async function uploadImage(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      await api.uploadAIAsset({
        file,
        title: title.trim() || undefined,
        asset_type: assetType,
        provider: 'user_upload',
        tags: [assetType, rightsTag(rightsStatus)].join(', '),
        prompt: notes.trim() || undefined
      });
      setFile(null);
      setTitle('');
      setNotes('');
      await refreshImages();
    } catch (err) {
      setError(err instanceof Error ? imageUploadError(err.message) : '上传图片素材失败');
    } finally {
      setBusy(false);
    }
  }

  async function archiveImage(assetId: number) {
    setBusy(true);
    setError('');
    try {
      await api.archiveAIAsset(assetId);
      await refreshImages();
    } catch (err) {
      setError(err instanceof Error ? err.message : '归档图片素材失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workspace-grid">
      <div className="panel">
        <div className="panel-kicker">图片素材</div>
        <h2>上传图片框、Logo 与贴片图</h2>
        <p className="form-note">
          素材授权请在上传前确认。Flashcutter 不负责判断某条素材是否可商用。
        </p>
        <form className="form-stack" onSubmit={uploadImage}>
          <label>
            素材标题
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={file?.name ?? '例如：新品竖版图片框'}
            />
          </label>
          <label>
            图片类型
            <select value={assetType} onChange={(event) => setAssetType(event.target.value)}>
              {imageAssetTypes.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            权利状态
            <select
              value={rightsStatus}
              onChange={(event) => setRightsStatus(event.target.value)}
            >
              {rightsStatusOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            来源和授权备注
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="记录来源、授权范围或仅参考原因。"
            />
          </label>
          <label>
            图片文件
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button className="primary-action" disabled={!file || busy}>
            {busy ? '上传中...' : '上传图片素材'}
          </button>
        </form>
        {error && <p className="error-banner">{error}</p>}
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">可生产素材</div>
            <h2>图片素材库</h2>
            <p>{assets.length} 个图片素材 · {usableCount} 个已授权可用于生产。</p>
          </div>
          <button className="secondary-action" type="button" onClick={refreshImages}>
            刷新
          </button>
        </div>
        <div className="filter-row image-filter-row">
          <select value={filterType} onChange={(event) => setFilterType(event.target.value)}>
            <option value="">全部图片类型</option>
            {imageAssetTypes.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        {filteredAssets.length === 0 ? (
          <div className="empty-action-state">
            <p className="empty-state">
              暂无图片素材。需要图片框、Logo 或贴片封面时，先上传并标记权利状态。
            </p>
          </div>
        ) : (
          <div className="image-asset-grid">
            {filteredAssets.map((asset) => {
              const rights = rightsStatusFromTags(asset.tags);
              return (
                <article key={asset.id} className="image-asset-card">
                  <img src={aiAssetFileUrl(asset.id)} alt="" loading="lazy" />
                  <div className="image-asset-body">
                    <div>
                      <strong>{asset.title}</strong>
                      <span>
                        {labelForAIAssetType(asset.asset_type)} · {formatAssetSize(asset.file_size_bytes)}
                      </span>
                    </div>
                    <span className={`rights-pill rights-pill-${rights || 'unknown'}`}>
                      {rights ? labelForRightsStatus(rights) : '未记录权利'}
                    </span>
                    <p>{asset.prompt || '未记录来源和授权备注。'}</p>
                    {rights !== 'licensed' && (
                      <p className="rights-note">
                        当前素材不可直接进入生产；确认授权后再作为模板参数选择。
                      </p>
                    )}
                    <div className="button-row">
                      <button
                        className="secondary-action"
                        type="button"
                        onClick={() => archiveImage(asset.id)}
                        disabled={busy}
                      >
                        归档
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

function imageUploadError(message: string) {
  if (message.includes('Unsupported AI asset type')) {
    return '图片类型暂不支持，请选择图片框、Logo、贴片封面、海报图或参考图。';
  }
  if (message.includes('AI asset must be an image or video file')) {
    return '请上传 JPG、PNG、WebP 等图片文件。';
  }
  return message;
}
