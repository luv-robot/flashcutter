import { FormEvent, useState } from 'react';
import { api } from '../api/client';
import type { Asset, TextRegionDetection } from '../api/types';
import { JsonBlock } from '../components/JsonBlock';
import { StatusBadge } from '../components/StatusBadge';

type SeedVideosPageProps = {
  assets: Asset[];
  onRefresh: () => Promise<void>;
  onSelectAsset: (assetId: number) => void;
  selectedAssetId: number | null;
};

export function SeedVideosPage({
  assets,
  onRefresh,
  onSelectAsset,
  selectedAssetId
}: SeedVideosPageProps) {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [filename, setFilename] = useState('');
  const [busy, setBusy] = useState(false);
  const [detectingAssetId, setDetectingAssetId] = useState<number | null>(null);
  const [textDetection, setTextDetection] = useState<TextRegionDetection | null>(null);

  async function uploadFile(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    try {
      await api.uploadAsset(file);
      setFile(null);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function importUrl(event: FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    try {
      await api.importAssetUrl(url.trim(), filename.trim() || undefined);
      setUrl('');
      setFilename('');
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function detectText(assetId: number) {
    setDetectingAssetId(assetId);
    try {
      const result = await api.detectTextRegions(assetId);
      setTextDetection(result);
      localStorage.setItem('flashcutter_last_cover_regions', JSON.stringify(result.cover_regions));
    } finally {
      setDetectingAssetId(null);
    }
  }

  return (
    <section className="workspace-grid">
      <div className="panel">
        <h2>素材导入</h2>
        <form onSubmit={uploadFile} className="form-stack">
          <label>
            本地视频素材
            <input
              type="file"
              accept="video/*"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button disabled={!file || busy} type="submit">
            上传
          </button>
        </form>
        <form onSubmit={importUrl} className="form-stack">
          <label>
            远程视频 URL
            <input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com/video.mp4"
            />
          </label>
          <label>
            文件名
            <input
              value={filename}
              onChange={(event) => setFilename(event.target.value)}
              placeholder="source.mp4"
            />
          </label>
          <button disabled={!url.trim() || busy} type="submit">
            导入 URL
          </button>
        </form>
        {textDetection && (
          <div className="result-box">
            <h3>文字区域检测结果</h3>
            <p>
              已为素材 #{textDetection.asset_id} 找到 {textDetection.regions.length} 个候选区域。
            </p>
            <JsonBlock value={{ cover_regions: textDetection.cover_regions }} />
          </div>
        )}
      </div>
      <div className="panel wide">
        <div className="panel-header">
          <h2>素材列表</h2>
          <button onClick={onRefresh}>刷新</button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>文件名</th>
                <th>状态</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <tr
                  key={asset.id}
                  className={asset.id === selectedAssetId ? 'selected-row' : ''}
                  onClick={() => onSelectAsset(asset.id)}
                >
                  <td>{asset.id}</td>
                  <td>{asset.original_filename}</td>
                  <td>
                    <StatusBadge value={asset.status} />
                  </td>
                  <td>{new Date(asset.created_at).toLocaleString()}</td>
                  <td>
                    <button
                      className="secondary-action"
                      onClick={(event) => {
                        event.stopPropagation();
                        void detectText(asset.id);
                      }}
                      disabled={detectingAssetId === asset.id || asset.status !== 'ready'}
                    >
                      {detectingAssetId === asset.id ? '检测中...' : '检测文字区域'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
