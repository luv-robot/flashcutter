import { FormEvent, useEffect, useRef, useState } from 'react';
import { api, clearAccessToken, getAccessToken, onAuthExpired, setAccessToken } from './api/client';
import type {
  Asset,
  AuthUser,
  GenerationTask,
  OutputReview,
  Template
} from './api/types';
import { AssetLibraryPage } from './pages/AssetLibraryPage';
import { CreateVariantsPage } from './pages/CreateVariantsPage';
import { PlatformPackagesPage } from './pages/PlatformPackagesPage';
import { ReviewOutputsPage } from './pages/ReviewOutputsPage';
import { TasksPage } from './pages/TasksPage';
import { TemplatesPage } from './pages/TemplatesPage';
import { WorkbenchPage } from './pages/WorkbenchPage';
import type { AssetTab } from './pages/AssetLibraryPage';

type View = 'workbench' | 'assets' | 'templates' | 'production' | 'tasks' | 'review' | 'packages';

const views: Array<{ id: View; label: string; description: string }> = [
  { id: 'workbench', label: '生产工作台', description: '今日生产概览、关键待办和批次入口。' },
  { id: 'assets', label: '素材库', description: '管理种子视频、视频片段、图片素材、配乐和组件参考。' },
  { id: 'templates', label: '模板方法', description: '创建和维护可复用的视频修改方法。' },
  { id: 'tasks', label: '队列与失败', description: '查看排队、运行、完成和失败处理状态。' },
  { id: 'review', label: '审核', description: '批次级审核成片，通过、要求修改、丢弃或拒绝。' },
  { id: 'packages', label: '投放包', description: '把过审视频整理成平台投放包。' }
];

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(() =>
    getAccessToken() ? { id: 0, phone: '已登录', display_name: null } : null
  );
  const [view, setView] = useState<View>('workbench');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [tasks, setTasks] = useState<GenerationTask[]>([]);
  const [outputs, setOutputs] = useState<OutputReview[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);
  const [reviewAssetId, setReviewAssetId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordMessage, setPasswordMessage] = useState('');
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [showReviewReminder, setShowReviewReminder] = useState(false);
  const [productionDialogRequest, setProductionDialogRequest] = useState(0);
  const [assetLibraryInitialTab, setAssetLibraryInitialTab] = useState<AssetTab>('seed-videos');
  const previousRunningCount = useRef(0);

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
    const token = getAccessToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api.me()
      .then((nextUser) => setUser(nextUser))
      .catch(() => {
        clearAccessToken();
        setUser(null);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    return onAuthExpired(() => {
      setUser(null);
      setAssets([]);
      setTemplates([]);
      setTasks([]);
      setOutputs([]);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (user) {
      void guardedRefresh();
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    const interval = window.setInterval(() => {
      if (tasks.some((task) => ['queued', 'waiting', 'segmenting', 'planning', 'rendering'].includes(task.status))) {
        void guardedRefresh();
      }
    }, 2500);
    return () => window.clearInterval(interval);
  }, [user, tasks]);

  useEffect(() => {
    const runningCount = tasks.filter((task) =>
      ['queued', 'waiting', 'segmenting', 'planning', 'rendering'].includes(task.status)
    ).length;
    const pendingReviewCount = outputs.filter(
      (output) => output.review_status === 'pending_review'
    ).length;
    if (
      previousRunningCount.current > 0 &&
      runningCount === 0 &&
      pendingReviewCount > 0 &&
      view !== 'review'
    ) {
      setShowReviewReminder(true);
    }
    previousRunningCount.current = runningCount;
  }, [tasks, outputs, view]);

  const currentView = views.find((item) => item.id === view) ?? views[0];

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

  async function submitPasswordChange(event: FormEvent) {
    event.preventDefault();
    setPasswordMessage('');
    if (newPassword !== confirmPassword) {
      setPasswordMessage('两次输入的新密码不一致。');
      return;
    }
    setPasswordBusy(true);
    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setPasswordMessage('密码已更新。');
    } catch (err) {
      setPasswordMessage(err instanceof Error ? err.message : '修改密码失败');
    } finally {
      setPasswordBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-lockup">
            <img src="/flashcutter-icon.svg" alt="" />
            <div>
              <h1>Flashcutter</h1>
              <p>短视频生产控制台</p>
            </div>
          </div>
        </div>
        <div className="user-block">
          <span>{user.display_name || user.phone}</span>
          <div className="user-actions">
            <button type="button" onClick={() => setShowPasswordForm((current) => !current)}>
              修改密码
            </button>
            <button type="button" onClick={logout}>退出登录</button>
          </div>
          {showPasswordForm && (
            <form className="password-form" onSubmit={submitPasswordChange}>
              <input
                type="password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                placeholder="当前密码"
              />
              <input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="新密码"
              />
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="确认新密码"
              />
              <button
                type="submit"
                disabled={!currentPassword || !newPassword || !confirmPassword || passwordBusy}
              >
                {passwordBusy ? '保存中...' : '保存密码'}
              </button>
              {passwordMessage && <small>{passwordMessage}</small>}
            </form>
          )}
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
            <h2>{currentView.label}</h2>
            <p>{currentView.description}</p>
          </div>
          <button className="secondary-action" onClick={guardedRefresh}>刷新全部</button>
        </header>
        {error && <div className="error-banner">{error}</div>}
        {loading ? (
          <div className="panel">正在加载工作台...</div>
        ) : (
          <>
            {view === 'workbench' && (
              <WorkbenchPage
                assets={assets}
                templates={templates}
                tasks={tasks}
                outputs={outputs}
                onCreateBatch={() => {
                  setView('production');
                  setProductionDialogRequest((current) => current + 1);
                }}
                onOpenQueue={() => setView('tasks')}
                onOpenReview={() => setView('review')}
                onOpenAssets={() => {
                  setAssetLibraryInitialTab('seed-videos');
                  setView('assets');
                }}
                onOpenMusic={() => {
                  setAssetLibraryInitialTab('music');
                  setView('assets');
                }}
                onOpenTemplates={() => setView('templates')}
                onOpenPackages={() => setView('packages')}
              />
            )}
            {view === 'assets' && (
              <AssetLibraryPage
                assets={assets}
                onRefresh={guardedRefresh}
                selectedAssetId={selectedAssetId}
                onSelectAsset={setSelectedAssetId}
                initialTab={assetLibraryInitialTab}
              />
            )}
            {view === 'templates' && (
              <TemplatesPage templates={templates} onRefresh={guardedRefresh} />
            )}
            {view === 'production' && (
              <CreateVariantsPage
                assets={assets}
                templates={templates}
                selectedAssetId={selectedAssetId}
                onSelectAsset={setSelectedAssetId}
                openSignal={productionDialogRequest}
                onTasksCreated={guardedRefresh}
                onRendered={guardedRefresh}
                onGoToReview={() => {
                  setReviewAssetId(selectedAssetId);
                  setView('review');
                }}
                onGoToAssets={() => setView('assets')}
                onGoToQueue={() => setView('tasks')}
              />
            )}
            {view === 'tasks' && (
              <TasksPage
                tasks={tasks}
                templates={templates}
                onRefresh={guardedRefresh}
                onCreateBatch={() => {
                  setView('production');
                  setProductionDialogRequest((current) => current + 1);
                }}
              />
            )}
            {view === 'review' && (
              <ReviewOutputsPage
                outputs={outputs}
                assets={assets}
                focusedAssetId={reviewAssetId}
                onRefresh={guardedRefresh}
                onOpenPackages={() => setView('packages')}
              />
            )}
            {view === 'packages' && <PlatformPackagesPage outputs={outputs} />}
          </>
        )}
      </main>
      {showReviewReminder && (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel review-reminder" role="dialog" aria-modal="true">
            <div className="panel-kicker">队列完成</div>
            <h2>任务已完成，请审核</h2>
            <p>
              渲染队列已经结束，当前有待审核成片。现在去审核可以继续批准、驳回或提出修改。
            </p>
            <div className="button-row">
              <button
                className="primary-action"
                type="button"
                onClick={() => {
                  setShowReviewReminder(false);
                  setView('review');
                }}
              >
                去审核
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() => setShowReviewReminder(false)}
              >
                稍后处理
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function AuthGate({
  onAuthenticated
}: {
  onAuthenticated: (token: string, user: AuthUser) => void;
}) {
  const allowRegistration = import.meta.env.VITE_ALLOW_REGISTRATION === 'true';
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
        mode === 'login' || !allowRegistration
          ? await api.login({ phone, password })
          : await api.register({
              phone,
              password,
              display_name: displayName || undefined
            });
      onAuthenticated(response.access_token, response.user);
    } catch (err) {
      setError(authErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div>
          <h1>Flashcutter</h1>
          <p>请使用分配的手机号和密码登录，登录后管理素材、渲染队列和成片审核。</p>
        </div>
        <form className="form-stack" onSubmit={submit}>
          <label>
            手机号
            <input value={phone} onChange={(event) => setPhone(event.target.value)} />
          </label>
          {allowRegistration && mode === 'register' && (
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
            {busy ? '处理中...' : mode === 'login' || !allowRegistration ? '登录' : '注册'}
          </button>
        </form>
        {allowRegistration ? (
          <button
            type="button"
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          >
            {mode === 'login' ? '创建账号' : '使用已有账号'}
          </button>
        ) : (
          <p className="auth-help">
            当前试用环境暂不开放自助注册。如需新账号，请联系管理员分配。
          </p>
        )}
      </section>
    </main>
  );
}

function authErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : '认证失败';
  if (message.includes('Invalid phone number or password')) {
    return '手机号或密码不正确，请检查分配账号信息。';
  }
  if (message.includes('Registration is disabled')) {
    return '当前试用环境暂不开放自助注册，请使用分配账号登录。';
  }
  if (message.includes('Authentication required')) {
    return '请先登录。';
  }
  return message;
}
