import { FormEvent, useEffect, useMemo, useState } from 'react';
import { api, clearAccessToken, getAccessToken, setAccessToken } from './api/client';
import type {
  Asset,
  AuthUser,
  GenerationTask,
  OutputReview,
  Template
} from './api/types';
import { CreateVariantsPage } from './pages/CreateVariantsPage';
import { ReviewOutputsPage } from './pages/ReviewOutputsPage';
import { SeedVideosPage } from './pages/SeedVideosPage';
import { TasksPage } from './pages/TasksPage';
import { TemplatesPage } from './pages/TemplatesPage';

type View = 'seeds' | 'templates' | 'variants' | 'tasks' | 'review';

const views: Array<{ id: View; label: string }> = [
  { id: 'seeds', label: '素材' },
  { id: 'templates', label: '模板' },
  { id: 'variants', label: '变体生产' },
  { id: 'tasks', label: '队列' },
  { id: 'review', label: '审核' }
];

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(() =>
    getAccessToken() ? { id: 0, phone: '已登录', display_name: null } : null
  );
  const [view, setView] = useState<View>('seeds');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [tasks, setTasks] = useState<GenerationTask[]>([]);
  const [outputs, setOutputs] = useState<OutputReview[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);
  const [reviewAssetId, setReviewAssetId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  async function refreshAll() {
    setError('');
    const [assetData, templateData, taskData, outputData] = await Promise.all([
      api.listAssets(),
      api.listTemplates(),
      api.listTasks(),
      api.listReviewOutputs()
    ]);
    setAssets(assetData);
    setTemplates(templateData);
    setTasks(taskData);
    setOutputs(outputData);
    if (!selectedAssetId && assetData.length > 0) {
      setSelectedAssetId(assetData[0].id);
    }
  }

  async function guardedRefresh() {
    try {
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载工作台数据失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (user) {
      void guardedRefresh();
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    const interval = window.setInterval(() => {
      if (tasks.some((task) => ['waiting', 'segmenting', 'planning', 'rendering'].includes(task.status))) {
        void guardedRefresh();
      }
    }, 2500);
    return () => window.clearInterval(interval);
  }, [user, tasks]);

  const stats = useMemo(
    () => [
      { label: '素材', value: assets.length },
      { label: '模板', value: templates.length },
      {
        label: '队列中',
        value: tasks.filter((task) =>
          ['waiting', 'segmenting', 'planning', 'rendering'].includes(task.status)
        ).length
      },
      {
        label: '待审核',
        value: outputs.filter((output) => output.review_status === 'pending_review').length
      }
    ],
    [assets.length, templates.length, tasks, outputs]
  );

  if (!user) {
    return (
      <AuthGate
        onAuthenticated={(token, nextUser) => {
          setAccessToken(token);
          setUser(nextUser);
        }}
      />
    );
  }

  function logout() {
    clearAccessToken();
    setUser(null);
    setAssets([]);
    setTemplates([]);
    setTasks([]);
    setOutputs([]);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>Flashcutter</h1>
          <p>短视频生产控制台</p>
        </div>
        <div className="user-block">
          <span>{user.display_name || user.phone}</span>
          <button onClick={logout}>退出登录</button>
        </div>
        <nav>
          {views.map((item) => (
            <button
              key={item.id}
              className={view === item.id ? 'active-nav' : ''}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <h2>{views.find((item) => item.id === view)?.label}</h2>
            <p>基于已授权素材，批量生成可审核的短视频广告变体。</p>
          </div>
          <button className="secondary-action" onClick={guardedRefresh}>刷新全部</button>
        </header>
        <section className="stats-grid">
          {stats.map((stat) => (
            <article key={stat.label} className="stat-tile">
              <span>{stat.label}</span>
              <strong>{stat.value}</strong>
            </article>
          ))}
        </section>
        {error && <div className="error-banner">{error}</div>}
        {loading ? (
          <div className="panel">正在加载工作台...</div>
        ) : (
          <>
            {view === 'seeds' && (
              <SeedVideosPage
                assets={assets}
                onRefresh={guardedRefresh}
                selectedAssetId={selectedAssetId}
                onSelectAsset={setSelectedAssetId}
              />
            )}
            {view === 'templates' && (
              <TemplatesPage templates={templates} onRefresh={guardedRefresh} />
            )}
            {view === 'variants' && (
              <CreateVariantsPage
                assets={assets}
                templates={templates}
                selectedAssetId={selectedAssetId}
                onSelectAsset={setSelectedAssetId}
                onTasksCreated={guardedRefresh}
                onRendered={guardedRefresh}
                onGoToReview={() => {
                  setReviewAssetId(selectedAssetId);
                  setView('review');
                }}
              />
            )}
            {view === 'tasks' && (
              <TasksPage
                tasks={tasks}
                templates={templates}
                onRefresh={guardedRefresh}
              />
            )}
            {view === 'review' && (
              <ReviewOutputsPage
                outputs={outputs}
                assets={assets}
                focusedAssetId={reviewAssetId}
                onRefresh={guardedRefresh}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

function AuthGate({
  onAuthenticated
}: {
  onAuthenticated: (token: string, user: AuthUser) => void;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response =
        mode === 'login'
          ? await api.login({ phone, password })
          : await api.register({
              phone,
              password,
              display_name: displayName || undefined
            });
      onAuthenticated(response.access_token, response.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : '认证失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div>
          <h1>Flashcutter</h1>
          <p>登录后管理素材、渲染队列和成片审核。</p>
        </div>
        <form className="form-stack" onSubmit={submit}>
          <label>
            手机号
            <input value={phone} onChange={(event) => setPhone(event.target.value)} />
          </label>
          {mode === 'register' && (
            <label>
              显示名称
              <input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
          )}
          <label>
            密码
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error && <p className="error-banner">{error}</p>}
          <button type="submit" disabled={busy}>
            {busy ? '处理中...' : mode === 'login' ? '登录' : '注册'}
          </button>
        </form>
        <button
          type="button"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
        >
          {mode === 'login' ? '创建账号' : '使用已有账号'}
        </button>
      </section>
    </main>
  );
}
