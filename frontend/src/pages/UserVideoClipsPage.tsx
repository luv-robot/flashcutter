import { FormEvent, useEffect, useMemo, useState } from 'react';
import { labelForAIAssetType, videoClipTypes } from '../api/assetDisplay';
import { aiAssetFileUrl, api } from '../api/client';
import type { AIAsset, AICloneJob, AICloneWorkflow } from '../api/types';

export function UserVideoClipsPage() {
  const [clips, setClips] = useState<AIAsset[]>([]);
  const [cloneJobs, setCloneJobs] = useState<AICloneJob[]>([]);
  const [cloneWorkflows, setCloneWorkflows] = useState<AICloneWorkflow[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [cloneTitle, setCloneTitle] = useState('');
  const [clipType, setClipType] = useState('broll');
  const [cloneType, setCloneType] = useState('broll');
  const [duration, setDuration] = useState(4);
  const [similarity, setSimilarity] = useState(0.75);
  const [motionStrength, setMotionStrength] = useState(0.45);
  const [referenceFrameStrategy, setReferenceFrameStrategy] = useState('auto_representative');
  const [simulatedQueueAhead, setSimulatedQueueAhead] = useState(3);
  const [tags, setTags] = useState('');
  const [cloneTags, setCloneTags] = useState('clone, test');
  const [notes, setNotes] = useState('');
  const [clonePrompt, setClonePrompt] = useState('');
  const [negativePrompt, setNegativePrompt] = useState('blurry, distorted, watermark');
  const [filterType, setFilterType] = useState('');
  const [filterTag, setFilterTag] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editType, setEditType] = useState('broll');
  const [editTags, setEditTags] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showUploadPanel, setShowUploadPanel] = useState(false);
  const hasActiveCloneJobs = cloneJobs.some((job) => isActiveCloneStatus(job.status));

  const totalSize = useMemo(
    () => clips.reduce((sum, clip) => sum + (clip.file_size_bytes ?? 0), 0),
    [clips]
  );

  async function refreshClips() {
    setError('');
    setClips(
      await api.listAIAssets({
        asset_kind: 'video',
        asset_type: filterType || undefined,
        tag: filterTag.trim() || undefined
      })
    );
  }

  async function refreshCloneJobs() {
    setCloneJobs(await api.listAICloneJobs());
  }

  useEffect(() => {
    void Promise.all([
      refreshClips(),
      refreshCloneJobs(),
      api.listAICloneWorkflows().then(setCloneWorkflows)
    ]).catch((err) => setError(err instanceof Error ? err.message : '加载视频片段库失败'));
  }, []);

  useEffect(() => {
    if (!hasActiveCloneJobs) return;
    const interval = window.setInterval(() => {
      void refreshCloneJobs()
        .then(() => refreshClips())
        .catch((err) => setError(err instanceof Error ? err.message : '刷新生成队列失败'));
    }, 2200);
    return () => window.clearInterval(interval);
  }, [hasActiveCloneJobs]);

  async function uploadClip(event: FormEvent) {
    event.preventDefault();
    if (!uploadFile) return;
    setBusy(true);
    setError('');
    try {
      await api.uploadAIAsset({
        file: uploadFile,
        title: title.trim() || undefined,
        asset_type: clipType,
        provider: 'user_upload',
        tags: tags.trim() || undefined,
        prompt: notes.trim() || undefined
      });
      setUploadFile(null);
      setTitle('');
      setTags('');
      setNotes('');
      await refreshClips();
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传视频片段失败');
    } finally {
      setBusy(false);
    }
  }

  async function createCloneJob(event: FormEvent) {
    event.preventDefault();
    if (!referenceFile || !clonePrompt.trim()) return;
    if (duration < 2 || duration > 8) {
      setError('仿制片段时长需要在 2-8 秒之间。');
      return;
    }
    if (referenceFile.type.startsWith('image/') && referenceFile.size > 10 * 1024 * 1024) {
      setError('参考图片超过 10MB，请先压缩后再提交。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api.createAICloneJob({
        file: referenceFile,
        title: cloneTitle.trim() || undefined,
        asset_type: cloneType,
        prompt: clonePrompt.trim(),
        negative_prompt: negativePrompt.trim() || undefined,
        tags: cloneTags.trim() || undefined,
        duration_seconds: duration,
        similarity,
        motion_strength: motionStrength,
        reference_frame_strategy: referenceFrameStrategy,
        simulated_queue_ahead: simulatedQueueAhead
      });
      setReferenceFile(null);
      setCloneTitle('');
      setClonePrompt('');
      await refreshCloneJobs();
      await refreshClips();
    } catch (err) {
      setError(cloneErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function cancelCloneJob(jobId: number) {
    setBusy(true);
    setError('');
    try {
      await api.cancelAICloneJob(jobId);
      await refreshCloneJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : '取消仿制任务失败');
    } finally {
      setBusy(false);
    }
  }

  async function retryCloneJob(jobId: number) {
    setBusy(true);
    setError('');
    try {
      await api.retryAICloneJob(jobId);
      await refreshCloneJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : '重新发起仿制任务失败');
    } finally {
      setBusy(false);
    }
  }

  async function archiveClip(assetId: number) {
    setBusy(true);
    setError('');
    try {
      await api.archiveAIAsset(assetId);
      await refreshClips();
    } catch (err) {
      setError(err instanceof Error ? err.message : '归档视频片段失败');
    } finally {
      setBusy(false);
    }
  }

  function startEdit(clip: AIAsset) {
    setEditingId(clip.id);
    setEditTitle(clip.title);
    setEditType(clip.asset_type);
    setEditTags(clip.tags.map((tag) => tag.tag).join(', '));
    setEditNotes(clip.prompt ?? '');
  }

  async function saveClipEdit(assetId: number) {
    setBusy(true);
    setError('');
    try {
      await api.updateAIAsset(assetId, {
        title: editTitle.trim() || undefined,
        asset_type: editType,
        prompt: editNotes.trim() || undefined,
        tags: editTags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean)
      });
      setEditingId(null);
      await refreshClips();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存视频片段失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workspace-grid production-grid">
      <div className="panel">
        <div className="panel-kicker">视频片段 / AI 仿制</div>
        <h2>生成可复用视频片段</h2>
        <form className="form-stack" onSubmit={createCloneJob}>
          <label>
            片段标题
            <input
              value={cloneTitle}
              onChange={(event) => setCloneTitle(event.target.value)}
              placeholder={referenceFile?.name ?? '例如：新品相似镜头'}
            />
          </label>
          <label>
            片段用途
            <select value={cloneType} onChange={(event) => setCloneType(event.target.value)}>
              {videoClipTypes.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <label>
            时长
            <input
              type="number"
              min="2"
              max="8"
              step="1"
              value={duration}
              onChange={(event) => setDuration(Number(event.target.value))}
            />
          </label>
          <label>
            相似度：{Math.round(similarity * 100)}%
            <input
              type="range"
              min="0.2"
              max="0.95"
              step="0.05"
              value={similarity}
              onChange={(event) => setSimilarity(Number(event.target.value))}
            />
          </label>
          <label>
            运动强度：{Math.round(motionStrength * 100)}%
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={motionStrength}
              onChange={(event) => setMotionStrength(Number(event.target.value))}
            />
          </label>
          <label>
            标签
            <input value={cloneTags} onChange={(event) => setCloneTags(event.target.value)} />
          </label>
          <label>
            仿制目标
            <textarea
              value={clonePrompt}
              onChange={(event) => setClonePrompt(event.target.value)}
              placeholder="描述想保留参考素材的哪些主体、风格、动作或镜头语言。"
            />
          </label>
          <label>
            排除内容
            <textarea
              value={negativePrompt}
              onChange={(event) => setNegativePrompt(event.target.value)}
              placeholder="例如：变形、模糊、水印、乱码文字。"
            />
          </label>
          <label>
            参考图片或视频
            <input
              type="file"
              accept="image/*,video/*"
              onChange={(event) => setReferenceFile(event.target.files?.[0] ?? null)}
            />
          </label>
          {referenceFile && (
            <div className="ai-clone-hint">
              <strong>{cloneInputHint(referenceFile)}</strong>
              <span>生成成功后会自动进入“我的视频片段库”，可在生产批次里作为 Hook、B-roll 或 CTA 片段使用。</span>
            </div>
          )}
          {referenceFile?.type.startsWith('video/') && (
            <label>
              参考帧
              <select
                value={referenceFrameStrategy}
                onChange={(event) => setReferenceFrameStrategy(event.target.value)}
              >
                <option value="auto_representative">自动选择代表帧</option>
                <option value="middle_frame">使用中间帧</option>
                <option value="first_frame">使用首帧</option>
              </select>
            </label>
          )}
          <label>
            测试排队状态
            <select
              value={simulatedQueueAhead}
              onChange={(event) => setSimulatedQueueAhead(Number(event.target.value))}
            >
              <option value={0}>不模拟等待</option>
              <option value={3}>前面 3 个任务</option>
              <option value={8}>前面 8 个任务</option>
              <option value={15}>前面 15 个任务</option>
            </select>
          </label>
          <button className="primary-action" disabled={!referenceFile || !clonePrompt.trim() || busy}>
            {busy ? '提交中...' : '加入仿制队列'}
          </button>
        </form>
        <small>
          仿制任务会按后端配置使用 mock 或 ComfyUI worker；可用 workflow：
          {' '}{cloneWorkflows.map((workflow) => workflow.name).join('、') || '加载中'}
        </small>
        <div className="secondary-panel">
          <div>
            <strong>已有可用片段？</strong>
            <span>上传入口收在这里，避免和仿制生成主流程混在一起。</span>
          </div>
          <button
            className="secondary-action"
            type="button"
            onClick={() => setShowUploadPanel((current) => !current)}
          >
            {showUploadPanel ? '收起上传' : '上传已有视频'}
          </button>
        </div>
        {showUploadPanel && (
          <form className="form-stack upload-drawer" onSubmit={uploadClip}>
            <label>
              片段标题
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={uploadFile?.name ?? '例如：产品旋转特写'}
              />
            </label>
            <label>
            片段用途
            <select value={clipType} onChange={(event) => setClipType(event.target.value)}>
                {videoClipTypes.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
            <label>
              标签
              <input
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="product, closeup, broll"
              />
            </label>
            <label>
              使用备注
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="记录这个片段适合放在开头、转场、结尾或产品证明位置。"
              />
            </label>
            <label>
              视频文件
              <input
                type="file"
                accept="video/*"
                onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <button className="secondary-action" disabled={!uploadFile || busy}>
              {busy ? '上传中...' : '上传到视频片段库'}
            </button>
          </form>
        )}
        {error && <p className="error-banner">{error}</p>}
      </div>
      <div className="panel wide">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">可复用片段</div>
            <h2>视频片段库</h2>
            <p>{clips.length} 个片段 · 系统素材、上传和生成片段统一管理 · {formatSize(totalSize)}</p>
          </div>
          <button className="secondary-action" onClick={refreshClips}>刷新</button>
        </div>
        <div className="filter-row">
          <select value={filterType} onChange={(event) => setFilterType(event.target.value)}>
            <option value="">全部用途</option>
            {videoClipTypes.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
          <input
            value={filterTag}
            onChange={(event) => setFilterTag(event.target.value)}
            placeholder="按标签筛选"
          />
          <button className="secondary-action" onClick={refreshClips}>应用筛选</button>
        </div>
        <div className="clone-queue-panel">
          <div className="panel-header compact">
            <div>
              <h3>生成队列</h3>
              <p>仿制任务会在这里显示排队、启动、预热、生成和入库状态。</p>
            </div>
            <button className="secondary-action" onClick={refreshCloneJobs}>刷新队列</button>
          </div>
          {cloneJobs.length === 0 ? (
            <p className="empty-state">暂无仿制任务。</p>
          ) : (
            <div className="clone-job-list">
              {cloneJobs.slice(0, 8).map((job) => (
                <article key={job.id} className="clone-job-card">
                  <div>
                    <strong>#{job.id} {job.title}</strong>
                    <span>{cloneStatusLabel(job)} · {job.reference_filename}</span>
                  </div>
                  <div className="progress-track">
                    <div style={{ width: `${Math.max(0, Math.min(100, job.progress_percent))}%` }} />
                  </div>
                  <small>{cloneTimingText(job)}</small>
                  {job.progress_message && <small>{job.progress_message}</small>}
                  {job.error_message && <small className="error">{job.error_message}</small>}
                  <div className="button-row">
                    {job.output_asset_id && <a href={`#clip-${job.output_asset_id}`}>查看片段</a>}
                    {isActiveCloneStatus(job.status) && (
                      <button className="secondary-action" type="button" onClick={() => cancelCloneJob(job.id)} disabled={busy}>
                        取消
                      </button>
                    )}
                    {['failed', 'cancelled', 'refunded'].includes(job.status) && (
                      <button className="secondary-action" type="button" onClick={() => retryCloneJob(job.id)} disabled={busy}>
                        重试
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
        {clips.length === 0 ? (
          <p className="empty-state">暂无视频片段。</p>
        ) : (
          <div className="ai-asset-grid">
            {clips.map((clip) => (
              <article key={clip.id} id={`clip-${clip.id}`} className="ai-asset-card">
                <div className="ai-asset-preview">
                  <video src={aiAssetFileUrl(clip.id)} controls muted />
                </div>
                <div className="ai-asset-body">
                  {editingId === clip.id ? (
                    <div className="clip-edit-form">
                      <input value={editTitle} onChange={(event) => setEditTitle(event.target.value)} />
                      <select value={editType} onChange={(event) => setEditType(event.target.value)}>
                        {videoClipTypes.map((item) => (
                          <option key={item.value} value={item.value}>{item.label}</option>
                        ))}
                      </select>
                      <input value={editTags} onChange={(event) => setEditTags(event.target.value)} />
                      <textarea value={editNotes} onChange={(event) => setEditNotes(event.target.value)} />
                    </div>
                  ) : (
                    <>
                      <div>
                        <strong>{clip.title}</strong>
                        <span>{labelForType(clip.asset_type)} · {formatDuration(clip.duration_seconds)}</span>
                      </div>
                      <p>{clip.prompt || '未记录使用备注'}</p>
                      <div className="tag-list">
                        {clip.tags.length === 0 ? (
                          <span>无标签</span>
                        ) : (
                          clip.tags.map((tag) => <span key={tag.id}>{tag.tag}</span>)
                        )}
                      </div>
                    </>
                  )}
                  <div className="ai-asset-meta">
                    <span>{formatSize(clip.file_size_bytes)}</span>
                    <span>{providerLabel(clip.provider)}</span>
                    <span>{clip.width ?? '-'}x{clip.height ?? '-'}</span>
                    <span>{clip.fps ? `${clip.fps.toFixed(1)}fps` : 'fps未知'}</span>
                  </div>
                  <div className="button-row">
                    {editingId === clip.id ? (
                      <>
                        <button className="secondary-action" type="button" onClick={() => saveClipEdit(clip.id)} disabled={busy}>
                          保存
                        </button>
                        <button className="secondary-action" type="button" onClick={() => setEditingId(null)} disabled={busy}>
                          取消
                        </button>
                      </>
                    ) : (
                      <button className="secondary-action" type="button" onClick={() => startEdit(clip)} disabled={busy}>
                        编辑
                      </button>
                    )}
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => archiveClip(clip.id)}
                      disabled={busy}
                    >
                      归档
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function labelForType(value: string) {
  return labelForAIAssetType(value);
}

function formatDuration(value: number | null) {
  return value ? `${value.toFixed(1)}s` : '时长未知';
}

function formatSize(value: number | null) {
  if (!value) return '0 KB';
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function providerLabel(value: string) {
  if (value === 'user_upload') return '上传';
  if (value === 'local_motion_mvp') return '生成';
  if (value === 'mock_liblib') return '生成';
  if (value === 'mock_ai_clone') return '仿制';
  if (value === 'comfyui_ai_clone') return '仿制';
  return value;
}

function cloneInputHint(file: File) {
  if (file.type.startsWith('image/')) {
    return '图片参考将进入 image_clone_video_v1 工作流';
  }
  if (file.type.startsWith('video/')) {
    return '视频参考会先自动取代表帧，再进入 video_reference_clone_v1 工作流';
  }
  return '参考文件会先做预检，再提交仿制工作流';
}

function cloneErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : '仿制任务没有创建成功';
  if (message.includes('2-8') || message.includes('duration')) {
    return '仿制片段时长需要在 2-8 秒之间。';
  }
  if (message.toLowerCase().includes('credits')) {
    return '仿制额度不足或额度预检失败；当前任务未扣费，请稍后重试或联系管理员补充额度。';
  }
  if (message.toLowerCase().includes('worker')) {
    return '仿制 worker 暂时不可用，任务没有提交成功；可以稍后重试。';
  }
  if (message.toLowerCase().includes('unsupported')) {
    return '参考文件格式暂不支持，请换成常见图片或视频格式。';
  }
  return message;
}

function isActiveCloneStatus(status: string) {
  return [
    'queued',
    'prechecking',
    'starting_worker',
    'warming_models',
    'submitting',
    'waiting_provider',
    'running',
    'postprocessing',
    'importing'
  ].includes(status);
}

function cloneStatusLabel(job: AICloneJob) {
  const labels: Record<string, string> = {
    queued: job.queue_position ? `排队中，第 ${job.queue_position} 位` : '排队中',
    prechecking: '预检中',
    starting_worker: '启动中',
    warming_models: '预热中',
    submitting: '提交中',
    waiting_provider: '等待生成服务',
    running: '生成中',
    postprocessing: '后处理中',
    importing: '入库中',
    succeeded: '已完成',
    failed: '失败',
    cancelled: '已取消',
    refunded: '已退款'
  };
  return labels[job.status] ?? job.status;
}

function cloneTimingText(job: AICloneJob) {
  if (job.status === 'queued') {
    return `已等待 ${formatClock(secondsSince(job.queue_entered_at))}`;
  }
  if (isActiveCloneStatus(job.status)) {
    const startedAt = job.started_at ?? job.queue_entered_at;
    return `已运行 ${formatClock(secondsSince(startedAt))}`;
  }
  if (job.elapsed_seconds != null) {
    return `总耗时 ${formatClock(job.elapsed_seconds)}`;
  }
  return '等待计时';
}

function secondsSince(value: string) {
  return Math.max(0, (Date.now() - parseBackendDate(value).getTime()) / 1000);
}

function parseBackendDate(value: string) {
  if (/[zZ]$|[+-]\d{2}:\d{2}$/.test(value)) {
    return new Date(value);
  }
  return new Date(`${value}Z`);
}

function formatClock(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
}
