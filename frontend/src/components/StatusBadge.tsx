type StatusBadgeProps = {
  value: string;
};

const labels: Record<string, string> = {
  uploaded: '已上传',
  probing: '分析中',
  ready: '就绪',
  failed: '失败',
  pending: '待处理',
  queued: '已创建',
  waiting: '排队中',
  segmenting: '分段中',
  planning: '规划中',
  rendering: '渲染中',
  completed: '已完成',
  cancelled: '已取消',
  pending_review: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
  needs_changes: '需修改',
  discarded: '已丢弃'
};

export function StatusBadge({ value }: StatusBadgeProps) {
  return <span className={`status status-${value}`}>{labels[value] ?? value.replace(/_/g, ' ')}</span>;
}
