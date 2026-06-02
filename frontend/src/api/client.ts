import type {
  AIAsset,
  AICloneJob,
  AICloneWorkflow,
  Asset,
  AuthResponse,
  CreativeReference,
  GenerationTask,
  MusicTrack,
  OutputReview,
  ProductionRunPreflight,
  ProductionRunPackageEstimate,
  TaskEvent,
  TaskRunResponse,
  Template,
  TextRegionDetection,
  VariantPreflight
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
const TOKEN_KEY = 'flashcutter_access_token';
const AUTH_EXPIRED_EVENT = 'flashcutter_auth_expired';

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch (error) {
    throw new Error(
      error instanceof TypeError
        ? '无法连接后端服务，请确认 127.0.0.1:8000 正在运行。'
        : '请求后端服务失败。'
    );
  }
  if (response.status === 401 && !path.startsWith('/api/auth/login')) {
    clearAccessToken();
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function onAuthExpired(handler: () => void): () => void {
  window.addEventListener(AUTH_EXPIRED_EVENT, handler);
  return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handler);
}

export function outputFileUrl(outputId: number): string {
  const token = getAccessToken();
  const tokenQuery = token ? `?access_token=${encodeURIComponent(token)}` : '';
  return `${API_BASE}/api/outputs/${outputId}/file${tokenQuery}`;
}

export function assetFileUrl(assetId: number): string {
  const token = getAccessToken();
  const tokenQuery = token ? `?access_token=${encodeURIComponent(token)}` : '';
  return `${API_BASE}/api/assets/${assetId}/file${tokenQuery}`;
}

export function musicFileUrl(trackId: number): string {
  const token = getAccessToken();
  const tokenQuery = token ? `?access_token=${encodeURIComponent(token)}` : '';
  return `${API_BASE}/api/music/${trackId}/file${tokenQuery}`;
}

export function aiAssetFileUrl(assetId: number): string {
  const token = getAccessToken();
  const tokenQuery = token ? `?access_token=${encodeURIComponent(token)}` : '';
  return `${API_BASE}/api/ai-assets/${assetId}/file${tokenQuery}`;
}

export function productionRunPackageUrl(productionRunId: number): string {
  const token = getAccessToken();
  const tokenQuery = token ? `?access_token=${encodeURIComponent(token)}` : '';
  return `${API_BASE}/api/production-runs/${productionRunId}/package${tokenQuery}`;
}

export const api = {
  register: (payload: { phone: string; password: string; display_name?: string }) =>
    request<AuthResponse>('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  login: (payload: { phone: string; password: string }) =>
    request<AuthResponse>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  me: () => request<AuthResponse['user']>('/api/auth/me'),
  changePassword: (payload: { current_password: string; new_password: string }) =>
    request<AuthResponse['user']>('/api/auth/password', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  listCreativeReferences: (filters?: {
    component_type?: string;
    industry?: string;
    rights_status?: string;
  }) => {
    const params = new URLSearchParams();
    if (filters?.component_type) params.set('component_type', filters.component_type);
    if (filters?.industry) params.set('industry', filters.industry);
    if (filters?.rights_status) params.set('rights_status', filters.rights_status);
    const query = params.toString();
    return request<CreativeReference[]>(`/api/creative-references${query ? `?${query}` : ''}`);
  },
  importCreativeReference: (payload: {
    url: string;
    component_type?: string;
    industry?: string;
    style_tags?: string[];
    notes?: string;
  }) =>
    request<CreativeReference>('/api/creative-references/import-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  createCreativeReference: (payload: {
    source_url: string;
    source_site?: string;
    title: string;
    description?: string;
    image_url?: string;
    rights_status?: string;
    component_type?: string;
    industry?: string;
    style_tags?: string[];
    layout_json?: Record<string, unknown>;
    notes?: string;
    is_active?: boolean;
  }) =>
    request<CreativeReference>('/api/creative-references', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  listAIAssets: (filters?: {
    asset_type?: string;
    asset_kind?: string;
    provider?: string;
    scope?: string;
    tag?: string;
    status?: string;
  }) => {
    const params = new URLSearchParams();
    Object.entries(filters ?? {}).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const query = params.toString();
    return request<AIAsset[]>(`/api/ai-assets${query ? `?${query}` : ''}`);
  },
  uploadAIAsset: (payload: {
    file: File;
    title?: string;
    asset_type: string;
    prompt?: string;
    provider?: string;
    tags?: string;
  }) => {
    const body = new FormData();
    body.append('file', payload.file);
    body.append('asset_type', payload.asset_type);
    if (payload.title) body.append('title', payload.title);
    if (payload.prompt) body.append('prompt', payload.prompt);
    if (payload.provider) body.append('provider', payload.provider);
    if (payload.tags) body.append('tags', payload.tags);
    return request<AIAsset>('/api/ai-assets/upload', {
      method: 'POST',
      body
    });
  },
  generateLocalMotionAIAsset: (payload: {
    file: File;
    title?: string;
    asset_type: string;
    prompt?: string;
    tags?: string;
    duration_seconds: number;
    width?: number;
    height?: number;
    fps?: number;
  }) => {
    const body = new FormData();
    body.append('file', payload.file);
    body.append('asset_type', payload.asset_type);
    body.append('duration_seconds', String(payload.duration_seconds));
    if (payload.width) body.append('width', String(payload.width));
    if (payload.height) body.append('height', String(payload.height));
    if (payload.fps) body.append('fps', String(payload.fps));
    if (payload.title) body.append('title', payload.title);
    if (payload.prompt) body.append('prompt', payload.prompt);
    if (payload.tags) body.append('tags', payload.tags);
    return request<AIAsset>('/api/ai-assets/generate/local-motion', {
      method: 'POST',
      body
    });
  },
  updateAIAsset: (
    assetId: number,
    payload: {
      title?: string;
      asset_type?: string;
      provider?: string;
      prompt?: string;
      tags?: string[];
    }
  ) =>
    request<AIAsset>(`/api/ai-assets/${assetId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  archiveAIAsset: (assetId: number) =>
    request<AIAsset>(`/api/ai-assets/${assetId}/archive`, {
      method: 'POST'
    }),
  listAICloneWorkflows: () => request<AICloneWorkflow[]>('/api/ai-clone/workflows'),
  listAICloneJobs: () => request<AICloneJob[]>('/api/ai-clone/jobs'),
  createAICloneJob: (payload: {
    file: File;
    workflow_id?: string;
    title?: string;
    prompt: string;
    negative_prompt?: string;
    asset_type: string;
    tags?: string;
    duration_seconds: number;
    similarity: number;
    motion_strength: number;
    reference_frame_strategy?: string;
    simulated_queue_ahead?: number;
  }) => {
    const body = new FormData();
    body.append('file', payload.file);
    body.append('prompt', payload.prompt);
    body.append('asset_type', payload.asset_type);
    body.append('duration_seconds', String(payload.duration_seconds));
    body.append('similarity', String(payload.similarity));
    body.append('motion_strength', String(payload.motion_strength));
    if (payload.reference_frame_strategy) {
      body.append('reference_frame_strategy', payload.reference_frame_strategy);
    }
    if (payload.simulated_queue_ahead != null) {
      body.append('simulated_queue_ahead', String(payload.simulated_queue_ahead));
    }
    if (payload.workflow_id) body.append('workflow_id', payload.workflow_id);
    if (payload.title) body.append('title', payload.title);
    if (payload.negative_prompt) body.append('negative_prompt', payload.negative_prompt);
    if (payload.tags) body.append('tags', payload.tags);
    return request<AICloneJob>('/api/ai-clone/jobs', {
      method: 'POST',
      body
    });
  },
  cancelAICloneJob: (jobId: number) =>
    request<AICloneJob>(`/api/ai-clone/jobs/${jobId}/cancel`, {
      method: 'POST'
    }),
  retryAICloneJob: (jobId: number) =>
    request<AICloneJob>(`/api/ai-clone/jobs/${jobId}/retry`, {
      method: 'POST'
    }),
  listMusic: () => request<MusicTrack[]>('/api/music'),
  uploadMusic: (payload: { file: File; title?: string }) => {
    const body = new FormData();
    body.append('file', payload.file);
    if (payload.title) {
      body.append('title', payload.title);
    }
    return request<MusicTrack>('/api/music/upload', {
      method: 'POST',
      body
    });
  },
  listAssets: () => request<Asset[]>('/api/assets'),
  uploadAsset: (file: File) => {
    const body = new FormData();
    body.append('file', file);
    return request<Asset>('/api/assets/upload', { method: 'POST', body });
  },
  importAssetUrl: (url: string, filename?: string) =>
    request<Asset>('/api/assets/import-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, filename: filename || undefined })
    }),
  detectTextRegions: (assetId: number) =>
    request<TextRegionDetection>(`/api/assets/${assetId}/text-regions/detect`, {
      method: 'POST'
    }),
  listTemplates: () => request<Template[]>('/api/templates'),
  createTemplate: (payload: {
    name: string;
    description?: string;
    version: number;
    json_spec: Record<string, unknown>;
    is_builtin?: boolean;
  }) =>
    request<Template>('/api/templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  updateTemplate: (
    templateId: number,
    payload: {
      name?: string;
      description?: string;
      version?: number;
      json_spec?: Record<string, unknown>;
      is_builtin?: boolean;
    }
  ) =>
    request<Template>(`/api/templates/${templateId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  validateTemplate: (jsonSpec: Record<string, unknown>) =>
    request<{
      valid: boolean;
      normalized_spec: Record<string, unknown>;
      warnings: string[];
    }>('/api/templates/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ json_spec: jsonSpec })
    }),
  listTasks: () => request<GenerationTask[]>('/api/tasks'),
  createBatchTasks: (payload: {
    name_prefix: string;
    asset_id: number;
    template_ids: number[];
    production_run_id?: number;
    params_json?: Record<string, unknown>;
  }) =>
    request<GenerationTask[]>('/api/tasks/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  renderVariants: (
    assetId: number,
    payload: {
      name_prefix: string;
      template_ids: number[];
      production_run_id?: number;
      params_json?: Record<string, unknown>;
    }
  ) =>
    request<OutputReview[]>(`/api/assets/${assetId}/render-variants`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  enqueueVariants: (
    assetId: number,
    payload: {
      name_prefix: string;
      template_ids: number[];
      production_run_id?: number;
      params_json?: Record<string, unknown>;
    }
  ) =>
    request<GenerationTask[]>(`/api/assets/${assetId}/render-variants/enqueue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  preflightVariants: (
    assetId: number,
    payload: {
      name_prefix: string;
      template_ids: number[];
      production_run_id?: number;
      params_json?: Record<string, unknown>;
    }
  ) =>
    request<VariantPreflight>(`/api/assets/${assetId}/render-variants/preflight`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  preflightProductionRun: (payload: {
    asset_ids: number[];
    template_ids: number[];
    runtime_values?: Record<string, unknown>;
    output_preset_id?: string;
    name_prefix: string;
  }) =>
    request<ProductionRunPreflight>('/api/production-runs/preflight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  enqueueProductionRun: (payload: {
    asset_ids: number[];
    template_ids: number[];
    runtime_values?: Record<string, unknown>;
    output_preset_id?: string;
    name_prefix: string;
    preflight_token?: string;
  }) =>
    request<GenerationTask[]>('/api/production-runs/enqueue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  runTask: (taskId: number, segmentSeconds?: number) =>
    request<TaskRunResponse>(`/api/tasks/${taskId}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(
        segmentSeconds ? { segment_seconds: segmentSeconds } : {}
      )
    }),
  enqueueTask: (taskId: number) =>
    request<GenerationTask>(`/api/tasks/${taskId}/enqueue`, {
      method: 'POST'
    }),
  listTaskEvents: (taskId: number) =>
    request<TaskEvent[]>(`/api/tasks/${taskId}/events`),
  listReviewOutputs: () => request<OutputReview[]>('/api/outputs/review'),
  listAssetOutputs: (assetId: number) =>
    request<OutputReview[]>(`/api/assets/${assetId}/outputs`),
  updateOutputReview: (
    outputId: number,
    payload: {
      review_status: string;
      review_notes?: string;
      reviewer_name?: string;
      change_request?: string;
      change_requests?: Array<{
        category: string;
        request: string;
        target?: string;
        priority?: string;
      }>;
      priority?: string;
      tags?: string[];
    }
  ) =>
    request<OutputReview>(`/api/outputs/${outputId}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  updateProductionRunStatus: (productionRunId: number, status: string) =>
    request<{ id: number; status: string }>(`/api/production-runs/${productionRunId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    }),
  estimateProductionRunPackage: (productionRunId: number) =>
    request<ProductionRunPackageEstimate>(
      `/api/production-runs/${productionRunId}/package/estimate`
    )
};
