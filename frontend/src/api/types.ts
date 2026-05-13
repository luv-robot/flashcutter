export type Asset = {
  id: number;
  original_filename: string;
  stored_filename: string;
  file_path: string;
  status: string;
  created_at: string;
};

export type TextRegionDetection = {
  asset_id: number;
  regions: Array<{
    x: number;
    y: number;
    width: number;
    height: number;
    confidence: number;
    source: string;
    text: string | null;
  }>;
  cover_regions: Array<{
    x: number;
    y: number;
    width: number;
    height: number;
    color: string;
  }>;
};

export type VariantPreflight = {
  asset_id: number;
  asset_filename: string;
  asset_duration_seconds: number | null;
  items: Array<{
    template_id: number;
    template_name: string;
    title: string | null;
    estimated_clip_count: number;
    estimated_duration_seconds: number | null;
    output_width: number | null;
    output_height: number | null;
    output_fps: number | null;
    fit: string;
    cover_region_count: number;
    text_overlay_count: number;
    playback_speed: number | null;
    mute_audio: boolean;
    warnings: string[];
  }>;
};

export type Template = {
  id: number;
  name: string;
  description: string | null;
  version: number;
  json_spec: Record<string, unknown>;
  is_builtin: boolean;
};

export type GenerationTask = {
  id: number;
  name: string;
  asset_id: number;
  template_id: number;
  status: string;
  progress_percent: number;
  progress_message: string | null;
  params_json: Record<string, unknown> | null;
  error_message: string | null;
};

export type TaskEvent = {
  id: number;
  task_id: number;
  status: string;
  progress_percent: number;
  message: string | null;
  error_message: string | null;
  created_at: string;
};

export type AuthUser = {
  id: number;
  phone: string;
  display_name: string | null;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

export type Segment = {
  id: number;
  asset_id: number;
  segment_index: number;
  start_time: number;
  end_time: number;
  duration_seconds: number;
  status: string;
};

export type RenderPlan = {
  id: number;
  task_id: number;
  plan_json: Record<string, unknown>;
  status: string;
};

export type OutputVideo = {
  id: number;
  task_id: number;
  render_plan_id: number;
  filename: string;
  file_path: string;
  status: string;
  review_status: string;
  review_notes: string | null;
  review_feedback_json: Record<string, unknown> | null;
};

export type OutputReview = {
  output_id: number;
  asset_id: number;
  asset_filename: string;
  task_id: number;
  task_name: string;
  template_id: number;
  template_name: string;
  template_version: number;
  render_plan_id: number;
  file_path: string;
  duration_seconds: number | null;
  file_size_bytes: number | null;
  status: string;
  review_status: string;
  review_notes: string | null;
  review_feedback: Record<string, unknown> | null;
  reviewed_at: string | null;
  created_at: string;
};

export type TaskRunResponse = {
  task: GenerationTask;
  segments: Segment[];
  render_plan: RenderPlan;
  output: OutputVideo;
};
