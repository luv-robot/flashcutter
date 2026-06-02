import { useState } from 'react';
import { api } from '../api/client';
import { templateTitle } from '../api/templateDisplay';
import type { GenerationTask, TaskEvent, Template } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

type TasksPageProps = {
  tasks: GenerationTask[];
  templates: Template[];
  onRefresh: () => Promise<void>;
  onCreateBatch: () => void;
};

const taskGroups = [
  {
    id: 'running',
    title: '运行中',
    description: '已经启动或正在渲染的任务。',
    statuses: ['segmenting', 'planning', 'rendering']
  },
  {
    id: 'queued',
    title: '排队中',
    description: '等待 worker 消化的任务，只显示你的队列。',
    statuses: ['queued', 'waiting']
  },
  {
    id: 'completed',
    title: '已完成，待审核',
    description: '完成后去审核页处理。',
    statuses: ['completed', 'succeeded']
  },
  {
    id: 'failed',
    title: '失败，可处理',
    description: '可以重试、回看事件或回到生产批次修正。',
    statuses: ['failed']
  }
];

export function TasksPage({ tasks, templates, onRefresh, onCreateBatch }: TasksPageProps) {
  const [runningTaskId, setRunningTaskId] = useState<number | null>(null);
  const [message, setMessage] = useState('');
  const [eventsByTask, setEventsByTask] = useState<Record<number, TaskEvent[]>>({});

  function templateName(templateId: number) {
    const template = templates.find((item) => item.id === templateId);
    return template ? templateTitle(template) : `#${templateId}`;
  }

  async function runTask(taskId: number) {
    setRunningTaskId(taskId);
    setMessage('');
    try {
      const result = await api.runTask(taskId);
      setMessage(
        `任务 #${result.task.id} 已渲染 ${result.segments.length} 个片段，生成成片 #${result.output.id}。`
      );
      await onRefresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '运行失败');
    } finally {
      setRunningTaskId(null);
    }
  }

  async function enqueueTask(taskId: number) {
    setRunningTaskId(taskId);
    setMessage('');
    try {
      const task = await api.enqueueTask(taskId);
      setMessage(`任务 #${task.id} 已进入渲染队列。`);
      await onRefresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '入队失败');
    } finally {
      setRunningTaskId(null);
    }
  }

  async function toggleEvents(taskId: number) {
    if (eventsByTask[taskId]) {
      setEventsByTask((current) => {
        const next = { ...current };
        delete next[taskId];
        return next;
      });
      return;
    }
    const events = await api.listTaskEvents(taskId);
    setEventsByTask((current) => ({ ...current, [taskId]: events }));
  }

  return (
    <section className="queue-page">
      <div className="panel queue-page-header">
        <div>
          <div className="panel-kicker">队列与失败</div>
          <h2>这里只显示你的任务</h2>
          <p>排队、运行、完成和失败处理集中在这里，不混入审核页。</p>
        </div>
        <button className="secondary-action" onClick={onRefresh}>刷新队列</button>
      </div>
      {message && <p className="notice">{message}</p>}

      <div className="queue-group-grid">
        {taskGroups.map((group) => {
          const groupTasks = tasks.filter((task) => group.statuses.includes(task.status));
          return (
            <section key={group.id} className="panel queue-group-panel">
              <div className="panel-header compact">
                <div>
                  <h2>{group.title}</h2>
                  <p>{group.description}</p>
                </div>
                <strong className="summary-number">{groupTasks.length}</strong>
              </div>
              <div className="queue-card-list">
                {groupTasks.length === 0 ? (
                  <p className="empty-state">暂无任务。</p>
                ) : (
                  groupTasks.map((task) => (
                    <article key={task.id} className={`queue-task-card queue-task-card-${group.id}`}>
                      <div className="queue-task-main">
                        <div>
                          <strong>#{task.id} {task.name}</strong>
                          <span>
                            所属批次 {task.production_run_id ? `#${task.production_run_id}` : '单素材'} · {templateName(task.template_id)}
                          </span>
                        </div>
                        <StatusBadge value={task.status} />
                      </div>
                      <div className="queue-stage-line">
                        <span>{task.progress_message || nextActionText(task.status)}</span>
                        <span>{task.progress_percent ?? 0}%</span>
                      </div>
                      <div className="progress-track">
                        <div style={{ width: `${Math.max(0, Math.min(100, task.progress_percent ?? 0))}%` }} />
                      </div>
                      {task.error_message && (
                        <div className="functional-error compact-error failure-guidance">
                          <strong>任务失败</strong>
                          <dl className="failure-detail-grid">
                            {failureGuidance(task.error_message).map((item) => (
                              <div key={item.label}>
                                <dt>{item.label}</dt>
                                <dd>{item.value}</dd>
                              </div>
                            ))}
                          </dl>
                        </div>
                      )}
                      <div className="button-row">
                        {['failed', 'queued', 'waiting'].includes(task.status) && (
                          <button
                            className="primary-action"
                            onClick={() => enqueueTask(task.id)}
                            disabled={runningTaskId === task.id}
                          >
                            重新发起
                          </button>
                        )}
                        {task.status !== 'rendering' && (
                          <button
                            className="secondary-action"
                            onClick={() => runTask(task.id)}
                            disabled={runningTaskId === task.id}
                          >
                            立即运行
                          </button>
                        )}
                        <button className="secondary-action" onClick={() => toggleEvents(task.id)}>
                          {eventsByTask[task.id] ? '收起详情' : '查看技术详情'}
                        </button>
                        {task.status === 'failed' && (
                          <button className="secondary-action" onClick={onCreateBatch}>
                            回生产批次修正
                          </button>
                        )}
                      </div>
                      {eventsByTask[task.id] && (
                        <div className="event-log">
                          {eventsByTask[task.id].length ? (
                            eventsByTask[task.id].map((event) => (
                              <div key={event.id} className="event-row">
                                <StatusBadge value={event.status} />
                                <span>{event.progress_percent}%</span>
                                <span>{event.message || event.error_message || '无消息'}</span>
                              </div>
                            ))
                          ) : (
                            <p>暂无事件记录。</p>
                          )}
                        </div>
                      )}
                    </article>
                  ))
                )}
              </div>
            </section>
          );
        })}
      </div>
    </section>
  );
}

function nextActionText(status: string) {
  const labels: Record<string, string> = {
    queued: '等待前序任务',
    waiting: '等待 worker',
    segmenting: '正在分段',
    planning: '正在生成渲染计划',
    rendering: '正在渲染',
    completed: '已完成，请审核',
    succeeded: '已完成，请审核',
    failed: '失败，可处理'
  };
  return labels[status] ?? '就绪';
}

function failureGuidance(message: string) {
  const lower = message.toLowerCase();
  if (lower.includes('rendered width') || lower.includes('rendered height')) {
    return [
      { label: '当前处境', value: '渲染已完成，但成片规格没有通过校验。' },
      { label: '失败步骤', value: '输出尺寸校验' },
      { label: '可读原因', value: '模板或本次输出规格与实际渲染出来的宽高不一致。' },
      { label: '下一步动作', value: '回到生产批次改输出规格，或在模板方法里选择更合适的预设后重新预检。' }
    ];
  }
  if (lower.includes('no ready segments') || lower.includes('ready segment')) {
    return [
      { label: '当前处境', value: '任务还没有可用视频片段，渲染无法开始。' },
      { label: '失败步骤', value: '素材分段' },
      { label: '可读原因', value: '种子视频未完成分段，或分段结果不可用。' },
      { label: '下一步动作', value: '先去素材库确认视频状态，必要时重新上传或重新发起分段后再入队。' }
    ];
  }
  if (lower.includes('music') && (lower.includes('missing') || lower.includes('not found'))) {
    return [
      { label: '当前处境', value: '模板需要的配乐没有找到，任务不能完整渲染。' },
      { label: '失败步骤', value: '配乐装配' },
      { label: '可读原因', value: '所选配乐文件缺失或已被归档。' },
      { label: '下一步动作', value: '在模板方法或本次参数中换一首可用配乐，再重新入队。' }
    ];
  }
  if (lower.includes('missing') || message.includes('缺少')) {
    return [
      { label: '当前处境', value: '模板要求的字段或素材还没补齐。' },
      { label: '失败步骤', value: '任务预检' },
      { label: '可读原因', value: message },
      { label: '下一步动作', value: '回生产批次补本次参数、图片或视频片段，然后重新运行预检。' }
    ];
  }
  if (lower.includes('ffmpeg')) {
    return [
      { label: '当前处境', value: '媒体处理命令执行失败。' },
      { label: '失败步骤', value: 'FFmpeg 渲染' },
      { label: '可读原因', value: '可能是源文件编码、尺寸、音频流或滤镜参数不兼容。' },
      { label: '下一步动作', value: '查看技术详情；若同素材反复失败，换源文件或降级模板效果后重试。' }
    ];
  }
  return [
    { label: '当前处境', value: '任务没有完成，需要查看详情后处理。' },
    { label: '失败步骤', value: '渲染流程' },
    { label: '可读原因', value: message },
    { label: '下一步动作', value: '先重试一次；若仍失败，回生产批次调整模板、素材或本次参数。' }
  ];
}
