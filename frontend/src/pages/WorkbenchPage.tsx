import type { Asset, GenerationTask, OutputReview, Template } from '../api/types';

type WorkbenchPageProps = {
  assets: Asset[];
  templates: Template[];
  tasks: GenerationTask[];
  outputs: OutputReview[];
  onCreateBatch: () => void;
  onOpenQueue: () => void;
  onOpenReview: () => void;
  onOpenAssets: () => void;
};

export function WorkbenchPage({
  assets,
  templates,
  tasks,
  outputs,
  onCreateBatch,
  onOpenQueue,
  onOpenReview,
  onOpenAssets
}: WorkbenchPageProps) {
  const queueCount = tasks.filter((task) => activeTaskStatuses.has(task.status)).length;
  const failedCount = tasks.filter((task) => task.status === 'failed').length;
  const pendingReviewCount = outputs.filter(
    (output) => output.review_status === 'pending_review'
  ).length;
  const approvedCount = outputs.filter((output) => output.review_status === 'approved').length;
  const recentTasks = tasks.slice(0, 4);
  const failedTasks = tasks.filter((task) => task.status === 'failed').slice(0, 3);

  return (
    <section className="workbench-page">
      <div className="workbench-hero panel">
        <div>
          <div className="panel-kicker">今日生产概览</div>
          <h2>批量套模板生产广告变体</h2>
          <p>围绕种子视频、模板方法、渲染队列、审核和投放包组织日常生产。</p>
        </div>
        <button className="primary-action" type="button" onClick={onCreateBatch}>
          创建生产批次
        </button>
      </div>

      <div className="stats-grid workbench-stats">
        <Metric label="可用素材" value={assets.length} onClick={onOpenAssets} />
        <Metric label="模板方法" value={templates.length} />
        <Metric label="队列中" value={queueCount} onClick={onOpenQueue} />
        <Metric label="待审核" value={pendingReviewCount} onClick={onOpenReview} />
        <Metric label="已通过" value={approvedCount} />
      </div>

      <div className="workbench-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>最近批次</h2>
              <p>最近创建或运行过的生产任务。</p>
            </div>
            <button className="secondary-action" type="button" onClick={onOpenQueue}>
              查看队列
            </button>
          </div>
          <div className="compact-card-list">
            {recentTasks.length === 0 ? (
              <p className="empty-state">还没有生产任务。</p>
            ) : (
              recentTasks.map((task) => (
                <article key={task.id} className="compact-card">
                  <div>
                    <strong>{task.name}</strong>
                    <span>
                      #{task.id} · 模板 #{task.template_id} · 素材 #{task.asset_id}
                    </span>
                  </div>
                  <span className={`queue-dot queue-dot-${task.status}`} />
                </article>
              ))
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>失败待处理</h2>
              <p>失败任务只在队列与失败里处理。</p>
            </div>
            <strong className="summary-number">{failedCount}</strong>
          </div>
          <div className="compact-card-list">
            {failedTasks.length === 0 ? (
              <p className="empty-state">暂无失败任务。</p>
            ) : (
              failedTasks.map((task) => (
                <article key={task.id} className="compact-card is-danger">
                  <div>
                    <strong>{task.name}</strong>
                    <span>{task.error_message || '需要查看技术详情。'}</span>
                  </div>
                  <button className="secondary-action" type="button" onClick={onOpenQueue}>
                    处理
                  </button>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="panel workbench-wide">
          <div className="panel-header">
            <div>
              <h2>待审核提醒</h2>
              <p>队列完成后，从这里进入审核并创建平台投放包。</p>
            </div>
            <button
              className="primary-action"
              type="button"
              onClick={onOpenReview}
              disabled={pendingReviewCount === 0}
            >
              去审核
            </button>
          </div>
          <div className="review-reminder-row">
            <strong>{pendingReviewCount} 条成片等待审核</strong>
            <span>通过后可进入投放包流程，生成巨量引擎、腾讯广告或阿里广告平台交付包。</span>
          </div>
        </section>
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  onClick
}: {
  label: string;
  value: number;
  onClick?: () => void;
}) {
  const content = (
    <>
      <span>{label}</span>
      <strong>{value}</strong>
    </>
  );
  if (!onClick) {
    return <article className="stat-tile">{content}</article>;
  }
  return (
    <button className="stat-tile stat-button" type="button" onClick={onClick}>
      {content}
    </button>
  );
}

const activeTaskStatuses = new Set(['queued', 'waiting', 'segmenting', 'planning', 'rendering']);
