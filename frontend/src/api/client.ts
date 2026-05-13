import type {
  Asset,
  AuthResponse,
  GenerationTask,
  OutputReview,
  TaskEvent,
  TaskRunResponse,
  Template,
  TextRegionDetection,
  VariantPreflight
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
const TOKEN_KEY = 'flashcutter_access_token';

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
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
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
      params_json?: Record<string, unknown>;
    }
  ) =>
    request<VariantPreflight>(`/api/assets/${assetId}/render-variants/preflight`, {
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
      priority?: string;
      tags?: string[];
    }
  ) =>
    request<OutputReview>(`/api/outputs/${outputId}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
};
