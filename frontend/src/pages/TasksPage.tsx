import { Fragment, useState } from 'react';
import { api } from '../api/client';
import { templateTitle } from '../api/templateDisplay';
import type { GenerationTask, TaskEvent, Template } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

type TasksPageProps = {
  tasks: GenerationTask[];
  templates: Template[];
  onRefresh: () => Promise<void>;
};

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
    <section className="panel queue-panel">
      <div className="panel-header">
        <div>
          <div className="panel-kicker">渲染队列</div>
          <h2>任务</h2>
        </div>
        <button className="secondary-action" onClick={onRefresh}>刷新</button>
      </div>
      {message && <p className="notice">{message}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>名称</th>
              <th>模板</th>
              <th>状态</th>
              <th>进度</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <Fragment key={task.id}>
                <tr>
                  <td>{task.id}</td>
                  <td>
                    {task.name}
                    {task.error_message && <p className="error">{task.error_message}</p>}
                  </td>
                  <td>{templateName(task.template_id)}</td>
                  <td>
                    <StatusBadge value={task.status} />
                  </td>
                  <td>
                    <div className="progress-cell">
                      <progress value={task.progress_percent ?? 0} max={100} />
                      <span>
                        {task.progress_percent ?? 0}% · {task.progress_message || '就绪'}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="button-row">
                      <button
                        className="primary-action"
                        onClick={() => enqueueTask(task.id)}
                        disabled={runningTaskId === task.id}
                      >
                        入队
                      </button>
                      <button
                        className="secondary-action"
                        onClick={() => runTask(task.id)}
                        disabled={runningTaskId === task.id}
                      >
                        立即运行
                      </button>
                      <button className="secondary-action" onClick={() => toggleEvents(task.id)}>事件</button>
                    </div>
                  </td>
                </tr>
                {eventsByTask[task.id] && (
                  <tr key={`${task.id}-events`}>
                    <td colSpan={6}>
                      <div className="event-log">
                        {eventsByTask[task.id].length ? (
                          eventsByTask[task.id].map((event) => (
                            <div key={event.id} className="event-row">
                              <StatusBadge value={event.status} />
                              <span>{event.progress_percent}%</span>
                              <span>{event.message || '无消息'}</span>
                              {event.error_message && <strong>{event.error_message}</strong>}
                            </div>
                          ))
                        ) : (
                          <p>暂无事件记录。</p>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
