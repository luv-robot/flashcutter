import { useState } from 'react';
import type { Asset } from '../api/types';
import { CreativeReferencesPage } from './CreativeReferencesPage';
import { MusicLibraryPage } from './MusicLibraryPage';
import { SeedVideosPage } from './SeedVideosPage';
import { UserVideoClipsPage } from './UserVideoClipsPage';

type AssetLibraryPageProps = {
  assets: Asset[];
  onRefresh: () => Promise<void>;
  selectedAssetId: number | null;
  onSelectAsset: (assetId: number) => void;
};

type AssetTab = 'seed-videos' | 'video-clips' | 'images' | 'music' | 'references';

const tabs: Array<{ id: AssetTab; label: string }> = [
  { id: 'seed-videos', label: '种子视频' },
  { id: 'video-clips', label: '视频片段' },
  { id: 'images', label: '图片素材' },
  { id: 'music', label: '配乐' },
  { id: 'references', label: '组件参考' }
];

export function AssetLibraryPage({
  assets,
  onRefresh,
  selectedAssetId,
  onSelectAsset
}: AssetLibraryPageProps) {
  const [tab, setTab] = useState<AssetTab>('seed-videos');

  return (
    <section className="asset-library-page">
      <div className="panel asset-library-header">
        <div>
          <div className="panel-kicker">素材库</div>
          <h2>生产素材统一入口</h2>
          <p>种子视频、可复用片段、配乐和组件参考按用途管理。</p>
        </div>
        <div className="segmented-tabs" role="tablist" aria-label="素材类型">
          {tabs.map((item) => (
            <button
              key={item.id}
              className={tab === item.id ? 'active-segment' : ''}
              type="button"
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'seed-videos' && (
        <SeedVideosPage
          assets={assets}
          onRefresh={onRefresh}
          selectedAssetId={selectedAssetId}
          onSelectAsset={onSelectAsset}
        />
      )}
      {tab === 'video-clips' && <UserVideoClipsPage />}
      {tab === 'images' && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">图片素材</div>
              <h2>图片框、Logo 与活动图</h2>
              <p>图片素材会用于模板方法中的图片框、品牌包装和本次参数。</p>
            </div>
            <button className="secondary-action" type="button" disabled>
              上传图片
            </button>
          </div>
          <p className="empty-state">图片素材接口尚未接入，当前可先在组件参考中沉淀图片框样式。</p>
        </section>
      )}
      {tab === 'music' && <MusicLibraryPage />}
      {tab === 'references' && <CreativeReferencesPage />}
    </section>
  );
}
