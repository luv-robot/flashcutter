import { FormEvent, useEffect, useMemo, useState } from 'react';
import { api, musicFileUrl } from '../api/client';
import type { MusicTrack } from '../api/types';

export function MusicLibraryPage() {
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const systemTracks = useMemo(
    () => tracks.filter((track) => track.scope === 'system'),
    [tracks]
  );
  const privateTracks = useMemo(
    () => tracks.filter((track) => track.scope !== 'system'),
    [tracks]
  );

  async function refreshMusic() {
    setError('');
    setTracks(await api.listMusic());
  }

  useEffect(() => {
    void refreshMusic().catch((err) =>
      setError(err instanceof Error ? err.message : '加载配乐库失败')
    );
  }, []);

  async function uploadTrack(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      await api.uploadMusic({ file, title: title.trim() || undefined });
      setFile(null);
      setTitle('');
      await refreshMusic();
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传配乐失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workspace-grid">
      <div className="panel">
        <div className="panel-kicker">私有库</div>
        <h2>上传配乐</h2>
        <p className="muted-copy">上传前请确认配乐授权。模板选择配乐后，会用它替换原视频声音。</p>
        <form className="form-stack" onSubmit={uploadTrack}>
          <label>
            配乐标题
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={file?.name ?? '例如：轻快开场'}
            />
          </label>
          <label>
            音频文件
            <input
              type="file"
              accept="audio/*"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button className="primary-action" disabled={!file || busy}>
            {busy ? '上传中...' : '上传到私有库'}
          </button>
        </form>
        {error && <p className="error-banner">{error}</p>}
      </div>
      <div className="panel wide">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">配乐库</div>
            <h2>系统公用与我的私有配乐</h2>
            <p>
              系统公用库 {systemTracks.length} 首，我的私有库 {privateTracks.length} 首。先试听再在模板方法里选择。
            </p>
          </div>
          <button className="secondary-action" onClick={refreshMusic}>刷新</button>
        </div>
        <MusicSection
          title="系统公用库"
          helper="所有试用用户可见，当前 free 曲目保留来源和 CC BY 授权信息。"
          tracks={systemTracks}
          emptyText="暂无系统配乐。"
        />
        <MusicSection
          title="我的私有库"
          helper="只给当前账号使用，适合客户指定品牌音乐或内部授权素材。"
          tracks={privateTracks}
          emptyText="暂无私有配乐。上传一首后即可在模板里使用。"
        />
      </div>
    </section>
  );
}

function MusicSection({
  title,
  helper,
  tracks,
  emptyText
}: {
  title: string;
  helper: string;
  tracks: MusicTrack[];
  emptyText: string;
}) {
  return (
    <div className="music-section">
      <div className="section-title-row">
        <div>
          <h3>{title}</h3>
          <p>{helper}</p>
        </div>
        <strong>{tracks.length}</strong>
      </div>
      {tracks.length === 0 ? (
        <p className="empty-state">{emptyText}</p>
      ) : (
        <div className="music-list">
          {tracks.map((track) => (
            <article key={track.id} className="music-row">
              <div>
                <strong>{track.title}</strong>
                <span>
                  {track.original_filename} · {formatDuration(track.duration_seconds)} ·{' '}
                  {formatBytes(track.file_size_bytes)}
                </span>
                <span>
                  {track.artist ? `${track.artist} · ` : ''}
                  {track.mood ? `${track.mood} · ` : ''}
                  {track.bpm ? `${track.bpm} BPM · ` : ''}
                  {track.license_name ?? '未记录授权'}
                  {track.source_url && (
                    <>
                      {' · '}
                      <a href={track.source_url} target="_blank" rel="noreferrer">
                        来源
                      </a>
                    </>
                  )}
                </span>
                {track.attribution_text && <small>{track.attribution_text}</small>}
              </div>
              <audio src={musicFileUrl(track.id)} controls />
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function formatDuration(value: number | null) {
  return value ? `${value.toFixed(1)}s` : '时长未知';
}

function formatBytes(value: number | null) {
  if (!value) return '大小未知';
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
