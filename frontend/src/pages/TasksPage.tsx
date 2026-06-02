import { useState } from 'react';
import { api } from '../api/client';
import { templateTitle } from '../api/templateDisplay';
import type { GenerationTask, TaskEvent, Template } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

type TasksPageProps = {
  tasks: GenerationTask[];
  templates: Template[];
  onRefresh: () => Promise<void>;
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

export function TasksPage({ tasks, templates, onRefresh }: TasksPageProps) {
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
                        <div className="functional-error compact-error">
                          <strong>任务失败</strong>
                          <p>{task.error_message}</p>
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
