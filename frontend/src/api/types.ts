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
    asset_id: number | null;
    asset_filename: string | null;
    template_id: number;
    template_name: string;
    status: string;
    title: string | null;
    estimated_clip_count: number;
    estimated_duration_seconds: number | null;
    output_width: number | null;
    output_height: number | null;
    output_fps: number | null;
    fit: string;
    cover_region_count: number;
    text_overlay_count: number;
    ai_asset_slot_count: number;
    selected_ai_asset_count: number;
    ai_asset_slots: Array<{
      slot: string;
      asset_id: number;
      asset_type: string;
      title: string;
      scope: string;
      provider: string;
      tags: string[];
      duration_seconds: number | null;
      position: string;
    }>;
    playback_speed: number | null;
    mute_audio: boolean;
    music_track_id: number | null;
    music_title: string | null;
    music_mode: string | null;
    music_volume: number | null;
    music_loop: boolean;
    warnings: string[];
    missing_fields: string[];
  }>;
};

export type ProductionRunPreflight = {
  preflight_token: string;
  summary: {
    asset_count: number;
    template_count: number;
    task_count: number;
    ready_count: number;
    warning_count: number;
    blocked_count: number;
  };
  items: VariantPreflight['items'];
  runtime_values: Record<string, unknown>;
  output_preset_id: string | null;
  name_prefix: string;
};

export type OpeningCopySuggestion = {
  id: string;
  text: string;
  angle: string;
  source: string;
  risk_level: string;
  length_level: string;
  locked: boolean;
};

export type StrongOpeningCopyRequest = {
  asset_id?: number;
  target_count: number;
  intensity: 'conservative' | 'balanced' | 'aggressive';
  product_name?: string;
  selling_points?: string[];
  audience?: string;
  forbidden_terms?: string[];
  user_notes?: string;
  language?: 'zh-CN' | 'en';
};

export type StrongOpeningCopyResponse = {
  provider: string;
  model: string | null;
  suggestions: OpeningCopySuggestion[];
  warnings: string[];
};

export type StrongOpeningExpansionRequest = StrongOpeningCopyRequest & {
  opening_texts?: string[];
  suggestions?: OpeningCopySuggestion[];
  output_preset_id?: string;
  name_prefix: string;
};

export type StrongOpeningExpansionPreflight = {
  preflight_token: string;
  summary: ProductionRunPreflight['summary'];
  items: VariantPreflight['items'];
  suggestions: OpeningCopySuggestion[];
  runtime_values: Record<string, unknown>;
  output_preset_id: string | null;
  name_prefix: string;
  template_id: number;
  template_name: string;
  warnings: string[];
};

export type Template = {
  id: number;
  name: string;
  description: string | null;
  version: number;
  json_spec: Record<string, unknown>;
  is_builtin: boolean;
};

export type CreativeReference = {
  id: number;
  source_url: string;
  source_site: string | null;
  title: string;
  description: string | null;
  image_url: string | null;
  rights_status: string;
  component_type: string;
  industry: string | null;
  style_tags: string[];
  layout_json: Record<string, unknown>;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MusicTrack = {
  id: number;
  user_id: number | null;
  title: string;
  original_filename: string;
  stored_filename: string;
  file_path: string;
  mime_type: string | null;
  file_size_bytes: number | null;
  duration_seconds: number | null;
  scope: string;
  artist: string | null;
  license_name: string | null;
  license_url: string | null;
  source_url: string | null;
  attribution_text: string | null;
  mood: string | null;
  bpm: number | null;
  is_active: boolean;
  created_at: string;
};

export type AIAsset = {
  id: number;
  user_id: number | null;
  scope: string;
  provider: string;
  asset_kind: string;
  asset_type: string;
  title: string;
  prompt: string | null;
  source_image_path: string | null;
  original_filename: string;
  stored_filename: string;
  file_path: string;
  mime_type: string | null;
  file_size_bytes: number | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  thumbnail_path: string | null;
  generation_cost: number | null;
  generation_time_seconds: number | null;
  usage_count: number;
  roi_score: number | null;
  avg_ctr_lift: number | null;
  review_reject_count: number;
  status: string;
  error_message: string | null;
  tags: Array<{ id: number; tag: string }>;
  created_at: string;
  updated_at: string;
};

export type AICloneWorkflow = {
  id: number;
  workflow_id: string;
  version: string;
  name: string;
  mode: string;
  provider: string;
  status: string;
  estimated_credits: number;
  estimated_seconds: number | null;
  params_schema_json: Record<string, unknown>;
};

export type AICloneJob = {
  id: number;
  user_id: number;
  workflow_id: string;
  mode: string;
  provider: string;
  provider_job_id: string | null;
  worker_id: number | null;
  reference_asset_id: number | null;
  reference_asset_type: string;
  reference_filename: string;
  title: string;
  prompt: string;
  negative_prompt: string | null;
  asset_type: string;
  tags_json: string[];
  input_params_json: Record<string, unknown>;
  status: string;
  estimated_credits: number;
  actual_credits: number | null;
  output_asset_id: number | null;
  error_message: string | null;
  queue_position: number | null;
  progress_percent: number;
  progress_message: string | null;
  estimated_seconds: number | null;
  wait_seconds: number | null;
  elapsed_seconds: number | null;
  retry_count: number;
  max_retries: number;
  simulated_queue_ahead: number;
  queue_entered_at: string;
  started_at: string | null;
  provider_started_at: string | null;
  postprocess_started_at: string | null;
  finished_at: string | null;
  last_heartbeat_at: string | null;
  created_at: string;
  updated_at: string;
};

export type GenerationTask = {
  id: number;
  name: string;
  production_run_id: number | null;
  revision_number: number;
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
  production_run_id: number | null;
  production_run_name: string | null;
  production_run_status: string | null;
  revision_number: number;
  task_id: number;
  task_name: string;
  template_id: number;
  template_name: string;
  template_version: number;
  render_plan_id: number;
  creative_goal: Record<string, unknown>;
  production_contract: Record<string, unknown>;
  render_plan: Record<string, unknown>;
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

export type ProductionRunPackageEstimate = {
  production_run_id: number;
  package_name: string;
  seed_filename: string;
  seed_size_bytes: number;
  approved_output_count: number;
  approved_output_size_bytes: number;
  total_size_bytes: number;
  missing_files: string[];
};

export type TaskRunResponse = {
  task: GenerationTask;
  segments: Segment[];
  render_plan: RenderPlan;
  output: OutputVideo;
};
