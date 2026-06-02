from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    stored_filename: str
    file_path: str
    status: str
    created_at: datetime


class AssetImportUrl(BaseModel):
    url: str
    filename: Optional[str] = None


class TextRegionRead(BaseModel):
    x: int
    y: int
    width: int
    height: int
    confidence: float
    source: str
    text: Optional[str] = None


class TextRegionDetectionRead(BaseModel):
    asset_id: int
    regions: List[TextRegionRead]
    cover_regions: List[Dict[str, Any]]


class CreativeReferenceCreate(BaseModel):
    source_url: str = Field(min_length=1, max_length=2048)
    source_site: Optional[str] = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    image_url: Optional[str] = Field(default=None, max_length=2048)
    rights_status: str = "reference_only"
    component_type: str = Field(default="layout_reference", max_length=64)
    industry: Optional[str] = Field(default=None, max_length=120)
    style_tags: List[str] = Field(default_factory=list)
    layout_json: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    is_active: bool = True

    @field_validator("rights_status")
    @classmethod
    def validate_rights_status(cls, value: str) -> str:
        allowed = {
            "reference_only",
            "needs_review",
            "licensed",
            "owned",
            "public_domain",
            "cc_by",
        }
        if value not in allowed:
            raise ValueError(f"rights_status must be one of: {', '.join(sorted(allowed))}")
        return value


class CreativeReferenceImportRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    component_type: Optional[str] = Field(default=None, max_length=64)
    industry: Optional[str] = Field(default=None, max_length=120)
    style_tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class CreativeReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_url: str
    source_site: Optional[str] = None
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    rights_status: str
    component_type: str
    industry: Optional[str] = None
    style_tags: List[str] = Field(default_factory=list)
    layout_json: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MusicTrackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    title: str
    original_filename: str
    stored_filename: str
    file_path: str
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None
    scope: str
    artist: Optional[str] = None
    license_name: Optional[str] = None
    license_url: Optional[str] = None
    source_url: Optional[str] = None
    attribution_text: Optional[str] = None
    mood: Optional[str] = None
    bpm: Optional[int] = None
    is_active: bool
    created_at: datetime


class AIAssetTagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tag: str


class AIAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    scope: str
    provider: str
    asset_kind: str
    asset_type: str
    title: str
    prompt: Optional[str] = None
    source_image_path: Optional[str] = None
    original_filename: str
    stored_filename: str
    file_path: str
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    thumbnail_path: Optional[str] = None
    generation_cost: Optional[float] = None
    generation_time_seconds: Optional[float] = None
    usage_count: int
    roi_score: Optional[float] = None
    avg_ctr_lift: Optional[float] = None
    review_reject_count: int
    status: str
    error_message: Optional[str] = None
    tags: List[AIAssetTagRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AIAssetUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    asset_type: Optional[str] = None
    prompt: Optional[str] = None
    provider: Optional[str] = Field(default=None, min_length=1, max_length=64)
    tags: Optional[List[str]] = None

    @field_validator("asset_type")
    @classmethod
    def validate_asset_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {"hook", "cta", "broll", "reaction", "meme", "product_motion"}
        if value not in allowed:
            raise ValueError(f"asset_type must be one of: {', '.join(sorted(allowed))}")
        return value


class AICloneWorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: str
    version: str
    name: str
    mode: str
    provider: str
    status: str
    estimated_credits: int
    estimated_seconds: Optional[int] = None
    params_schema_json: Dict[str, Any] = Field(default_factory=dict)


class AICloneJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    workflow_id: str
    mode: str
    provider: str
    provider_job_id: Optional[str] = None
    worker_id: Optional[int] = None
    reference_asset_id: Optional[int] = None
    reference_asset_type: str
    reference_filename: str
    title: str
    prompt: str
    negative_prompt: Optional[str] = None
    asset_type: str
    tags_json: List[str] = Field(default_factory=list)
    input_params_json: Dict[str, Any] = Field(default_factory=dict)
    status: str
    estimated_credits: int
    actual_credits: Optional[int] = None
    output_asset_id: Optional[int] = None
    error_message: Optional[str] = None
    queue_position: Optional[int] = None
    progress_percent: int
    progress_message: Optional[str] = None
    estimated_seconds: Optional[int] = None
    wait_seconds: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    retry_count: int
    max_retries: int
    simulated_queue_ahead: int
    queue_entered_at: datetime
    started_at: Optional[datetime] = None
    provider_started_at: Optional[datetime] = None
    postprocess_started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AICloneJobEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    status: str
    progress_percent: int
    message: Optional[str] = None
    error_message: Optional[str] = None
    raw_response_json: Optional[Dict[str, Any]] = None
    created_at: datetime


class AuthRegisterRequest(BaseModel):
    phone: str
    password: str
    display_name: Optional[str] = None


class AuthLoginRequest(BaseModel):
    phone: str
    password: str


class AuthPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class AuthUserRead(BaseModel):
    id: int
    phone: str
    display_name: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserRead


class SegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    segment_index: int
    start_time: float
    end_time: float
    duration_seconds: float
    status: str


class TemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    version: int
    json_spec: Dict[str, Any]
    is_builtin: bool


class TemplateOutputSpec(BaseModel):
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    fps: Optional[float] = Field(default=None, gt=0, le=120)
    format: str = "mp4"

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        if value != "mp4":
            raise ValueError("Only mp4 output is supported by the MVP renderer")
        return value

    @model_validator(mode="after")
    def validate_dimensions(self) -> "TemplateOutputSpec":
        if (self.width is None) != (self.height is None):
            raise ValueError("output.width and output.height must be set together")
        if self.width is not None and self.width % 2 != 0:
            raise ValueError("output.width must be an even number for H.264 output")
        if self.height is not None and self.height % 2 != 0:
            raise ValueError("output.height must be an even number for H.264 output")
        return self


class TemplateSelectionSpec(BaseModel):
    mode: str = "all"
    count: Optional[int] = Field(default=None, ge=1)
    max_total_duration: Optional[float] = Field(default=None, gt=0)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in {"all", "all_ready_segments", "first_n"}:
            raise ValueError("selection.mode must be all, all_ready_segments, or first_n")
        return value


class TemplateSegmentsSpec(BaseModel):
    segment_seconds: float = Field(default=3.0, gt=0, le=60)


class TemplateLayoutSpec(BaseModel):
    fit: str = "original"

    @field_validator("fit")
    @classmethod
    def validate_fit(cls, value: str) -> str:
        if value not in {"original", "cover", "contain"}:
            raise ValueError("layout.fit must be original, cover, or contain")
        return value


class TemplateCoverRegion(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    color: str = "black@0.82"


class TemplateTextOverlay(BaseModel):
    text: str = Field(min_length=1, max_length=120)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    font_size: int = Field(default=54, ge=12, le=180)
    font_color: str = "white"
    box_color: Optional[str] = "black@0.62"
    box_padding: int = Field(default=18, ge=0, le=80)


class TemplateTransformationsSpec(BaseModel):
    orientation: str = "normal"
    visual_style: str = "natural"
    finishing_style: str = "none"
    motion_style: str = "none"
    transition_style: str = "hard_cut"
    texture_style: str = "none"
    brightness: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    contrast: Optional[float] = Field(default=None, ge=0.0, le=3.0)
    saturation: Optional[float] = Field(default=None, ge=0.0, le=3.0)
    playback_speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    volume: Optional[float] = Field(default=None, ge=0.0, le=3.0)
    mute_audio: bool = False
    cover_regions: List[TemplateCoverRegion] = Field(default_factory=list)
    text_overlays: List[TemplateTextOverlay] = Field(default_factory=list)

    @field_validator("orientation")
    @classmethod
    def validate_orientation(cls, value: str) -> str:
        allowed = {"normal", "mirror_horizontal"}
        if value not in allowed:
            raise ValueError(f"orientation must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("visual_style")
    @classmethod
    def validate_visual_style(cls, value: str) -> str:
        allowed = {
            "natural",
            "clean_ad",
            "warm_lifestyle",
            "cool_tech",
            "punchy_social",
            "soft_beauty",
        }
        if value not in allowed:
            raise ValueError(f"visual_style must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("finishing_style")
    @classmethod
    def validate_finishing_style(cls, value: str) -> str:
        allowed = {"none", "sharpen", "soften", "film_grain", "vignette"}
        if value not in allowed:
            raise ValueError(f"finishing_style must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("motion_style")
    @classmethod
    def validate_motion_style(cls, value: str) -> str:
        allowed = {"none", "slow_push_in", "slow_pan", "light_rotate", "social_pulse"}
        if value not in allowed:
            raise ValueError(f"motion_style must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("transition_style")
    @classmethod
    def validate_transition_style(cls, value: str) -> str:
        allowed = {"hard_cut", "flash_white", "flash_black", "soft_fade"}
        if value not in allowed:
            raise ValueError(f"transition_style must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("texture_style")
    @classmethod
    def validate_texture_style(cls, value: str) -> str:
        allowed = {"none", "warm_light_leak", "cool_light_leak", "subtle_grid"}
        if value not in allowed:
            raise ValueError(f"texture_style must be one of: {', '.join(sorted(allowed))}")
        return value


class TemplateCreativeGoal(BaseModel):
    title: Optional[str] = None
    audience: Optional[str] = None
    selling_points: List[str] = Field(default_factory=list)
    tone: Optional[str] = None


class TemplateProductionContract(BaseModel):
    use_case: Optional[str] = None
    operator_notes: Optional[str] = None
    review_checklist: List[str] = Field(default_factory=list)


class TemplateMusicSpec(BaseModel):
    mode: str = "replace"
    track_id: Optional[int] = None
    volume: float = Field(default=1.0, ge=0.0, le=3.0)
    loop: bool = True

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value != "replace":
            raise ValueError("Only replace music mode is supported")
        return value


class TemplateEditingSpec(BaseModel):
    cut_style: str = "fixed_interval"
    clip_duration_seconds: float = Field(default=3.0, gt=0, le=60)
    target_duration_seconds: Optional[float] = Field(default=None, gt=0)
    max_clip_count: Optional[int] = Field(default=None, ge=1)
    pacing: str = "medium"
    keep_original_order: bool = True

    @field_validator("cut_style")
    @classmethod
    def validate_cut_style(cls, value: str) -> str:
        if value != "fixed_interval":
            raise ValueError("Only fixed_interval cut_style is supported by the MVP renderer")
        return value


class TemplateDeliverySpec(BaseModel):
    aspect_ratio: str = "source"
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    fps: Optional[float] = Field(default=None, gt=0, le=120)
    format: str = "mp4"
    fit: str = "original"

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        if value != "mp4":
            raise ValueError("Only mp4 output is supported by the MVP renderer")
        return value

    @field_validator("fit")
    @classmethod
    def validate_fit(cls, value: str) -> str:
        if value not in {"original", "cover", "contain"}:
            raise ValueError("delivery.fit must be original, cover, or contain")
        return value

    @model_validator(mode="after")
    def validate_dimensions(self) -> "TemplateDeliverySpec":
        if (self.width is None) != (self.height is None):
            raise ValueError("delivery.width and delivery.height must be set together")
        if self.width is not None and self.width % 2 != 0:
            raise ValueError("delivery.width must be an even number for H.264 output")
        if self.height is not None and self.height % 2 != 0:
            raise ValueError("delivery.height must be an even number for H.264 output")
        return self


class TemplateOutputPresetSpec(BaseModel):
    preset_id: str
    label: str
    description: Optional[str] = None
    aspect_ratio: str = "source"
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    fit: str = "original"
    fps: Optional[float] = Field(default=30.0, gt=0, le=120)
    format: str = "mp4"

    @field_validator("fit")
    @classmethod
    def validate_fit(cls, value: str) -> str:
        if value not in {"original", "cover", "contain"}:
            raise ValueError("output preset fit must be original, cover, or contain")
        return value

    def to_delivery(self) -> TemplateDeliverySpec:
        return TemplateDeliverySpec(
            aspect_ratio=self.aspect_ratio,
            width=self.width,
            height=self.height,
            fps=self.fps,
            format=self.format,
            fit=self.fit,
        )


class CompiledTemplateSpec(BaseModel):
    type: str = "concat"
    creative_goal: TemplateCreativeGoal = Field(default_factory=TemplateCreativeGoal)
    production_contract: TemplateProductionContract = Field(
        default_factory=TemplateProductionContract
    )
    editing: Optional[TemplateEditingSpec] = None
    delivery: Optional[TemplateDeliverySpec] = None
    review_notes: Optional[str] = None
    output: TemplateOutputSpec = Field(default_factory=TemplateOutputSpec)
    selection: TemplateSelectionSpec = Field(default_factory=TemplateSelectionSpec)
    segments: TemplateSegmentsSpec = Field(default_factory=TemplateSegmentsSpec)
    layout: TemplateLayoutSpec = Field(default_factory=TemplateLayoutSpec)
    music: TemplateMusicSpec = Field(default_factory=TemplateMusicSpec)
    transformations: TemplateTransformationsSpec = Field(
        default_factory=TemplateTransformationsSpec
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value != "concat":
            raise ValueError("Only concat templates are supported by the MVP renderer")
        return value


class TemplateSlotRequirement(BaseModel):
    slot: str
    role: str = "source_segment"
    asset_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    min_duration_seconds: Optional[float] = Field(default=None, gt=0)
    max_duration_seconds: Optional[float] = Field(default=None, gt=0)
    optional: bool = False
    notes: Optional[str] = None


class TemplateBlueprintSpec(BaseModel):
    blueprint_id: str
    name: str
    creative_goal: TemplateCreativeGoal = Field(default_factory=TemplateCreativeGoal)
    production_contract: TemplateProductionContract = Field(
        default_factory=TemplateProductionContract
    )
    editing: TemplateEditingSpec = Field(default_factory=TemplateEditingSpec)
    slots: List[TemplateSlotRequirement] = Field(default_factory=list)


class TemplateRenderPresetSpec(BaseModel):
    preset_id: str
    name: str
    delivery: TemplateDeliverySpec = Field(default_factory=TemplateDeliverySpec)
    safe_zones: List[TemplateCoverRegion] = Field(default_factory=list)


class TemplateStylePackSpec(BaseModel):
    style_pack_id: str
    name: str
    transformations: TemplateTransformationsSpec = Field(
        default_factory=TemplateTransformationsSpec
    )


class TemplateCopyPackSpec(BaseModel):
    copy_pack_id: str
    name: str
    text_overlays: List[TemplateTextOverlay] = Field(default_factory=list)
    cover_regions: List[TemplateCoverRegion] = Field(default_factory=list)
    review_checklist: List[str] = Field(default_factory=list)


class TemplateSlotBinding(BaseModel):
    source_type: str = "source_segment"
    asset_id: Optional[int] = None
    asset_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    duration: Optional[List[float]] = None
    selection: Optional[str] = None
    optional: bool = False

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        allowed = {"source_segment", "ai_asset", "uploaded_asset", "copy_pack"}
        if value not in allowed:
            raise ValueError(f"source_type must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, value: Optional[List[float]]) -> Optional[List[float]]:
        if value is None:
            return value
        if len(value) != 2 or value[0] <= 0 or value[1] <= 0 or value[0] > value[1]:
            raise ValueError("duration must be [min_seconds, max_seconds]")
        return value


class TemplateSpec(BaseModel):
    schema_version: int = 2
    type: str = "variant_recipe"
    recipe_id: str
    name: str
    blueprint: TemplateBlueprintSpec
    render_preset: TemplateRenderPresetSpec
    style_pack: TemplateStylePackSpec
    copy_pack: Optional[TemplateCopyPackSpec] = None
    slot_bindings: Dict[str, TemplateSlotBinding] = Field(default_factory=dict)
    music: TemplateMusicSpec = Field(default_factory=TemplateMusicSpec)
    review_notes: Optional[str] = None

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        if value != 2:
            raise ValueError("Only template schema_version 2 is supported")
        return value

    @field_validator("type")
    @classmethod
    def validate_recipe_type(cls, value: str) -> str:
        if value != "variant_recipe":
            raise ValueError("Only variant_recipe templates are supported")
        return value


class TemplateV3InputRequirements(BaseModel):
    min_seed_duration_seconds: Optional[float] = Field(default=None, gt=0)
    accepted_seed_ratios: List[str] = Field(default_factory=list)
    requires_audio: bool = False


class TemplateV3Operation(BaseModel):
    type: str
    slot: Optional[str] = None
    label: Optional[str] = None
    required: bool = False
    output_preset_id: Optional[str] = None
    placement: Optional[str] = None
    position: Optional[str] = None
    safe_margin: Optional[int] = Field(default=None, ge=0)
    region: Optional[str] = None
    color: Optional[str] = None
    field: Optional[str] = None
    style: Optional[str] = None
    fit: Optional[str] = None
    audio_policy: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        allowed = {
            "prepend_clip",
            "append_clip",
            "overlay_image",
            "overlay_frame",
            "overlay_logo",
            "cover_region",
            "text_placeholder",
            "replace_music",
            "resize_canvas",
            "trim_seed",
        }
        if value not in allowed:
            raise ValueError(f"operation type must be one of: {', '.join(sorted(allowed))}")
        return value


class TemplateV3RuntimeField(BaseModel):
    key: str
    label: str
    field_type: str
    asset_kind: Optional[str] = None
    asset_type: Optional[str] = None
    max_length: Optional[int] = Field(default=None, gt=0)
    required: bool = False

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, value: str) -> str:
        allowed = {"asset", "text", "boolean", "choice", "number", "music"}
        if value not in allowed:
            raise ValueError(f"runtime field type must be one of: {', '.join(sorted(allowed))}")
        return value


class TemplateSpecV3(BaseModel):
    schema_version: int = 3
    type: str = "video_modification_template"
    template_id: str
    name: str
    category: str = "packaging"
    use_case: Optional[str] = None
    input_requirements: TemplateV3InputRequirements = Field(
        default_factory=TemplateV3InputRequirements
    )
    operations: List[TemplateV3Operation] = Field(default_factory=list)
    runtime_fields: List[TemplateV3RuntimeField] = Field(default_factory=list)
    output_preset_id: str = "source_original"
    review_checklist: List[str] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        if value != 3:
            raise ValueError("Only template schema_version 3 is supported")
        return value

    @field_validator("type")
    @classmethod
    def validate_template_type(cls, value: str) -> str:
        if value != "video_modification_template":
            raise ValueError("v3 templates must use type video_modification_template")
        return value


def validate_template_json_spec(value: Dict[str, Any]) -> Dict[str, Any]:
    schema_version = value.get("schema_version")
    if schema_version == 2:
        TemplateSpec.model_validate(value)
    elif schema_version == 3:
        TemplateSpecV3.model_validate(value)
    else:
        raise ValueError("template json_spec must use schema_version 2 or 3")
    return value


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    version: int = 1
    json_spec: Dict[str, Any]
    is_builtin: bool = False

    @field_validator("json_spec")
    @classmethod
    def validate_json_spec(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return validate_template_json_spec(value)


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[int] = None
    json_spec: Optional[Dict[str, Any]] = None
    is_builtin: Optional[bool] = None

    @field_validator("json_spec")
    @classmethod
    def validate_json_spec(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if value is None:
            return value
        return validate_template_json_spec(value)


class TemplateValidationRequest(BaseModel):
    json_spec: Dict[str, Any]

    @field_validator("json_spec")
    @classmethod
    def validate_json_spec(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return validate_template_json_spec(value)


class TemplateValidationRead(BaseModel):
    valid: bool
    normalized_spec: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)


class GenerationTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    production_run_id: Optional[int] = None
    revision_number: int = 1
    asset_id: int
    template_id: int
    status: str
    progress_percent: int
    progress_message: Optional[str] = None
    params_json: Optional[Dict[str, Any]]
    error_message: Optional[str] = None


class TaskEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    status: str
    progress_percent: int
    message: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


class GenerationTaskCreate(BaseModel):
    name: str
    asset_id: int
    template_id: int
    params_json: Optional[Dict[str, Any]] = None


class GenerationTaskBatchCreate(BaseModel):
    name_prefix: str
    asset_id: int
    template_ids: List[int]
    production_run_id: Optional[int] = None
    params_json: Optional[Dict[str, Any]] = None


class RenderVariantsRequest(BaseModel):
    name_prefix: str
    template_ids: List[int]
    production_run_id: Optional[int] = None
    params_json: Optional[Dict[str, Any]] = None


class VariantPreflightItem(BaseModel):
    asset_id: Optional[int] = None
    asset_filename: Optional[str] = None
    template_id: int
    template_name: str
    status: str = "ready"
    title: Optional[str] = None
    estimated_clip_count: int
    estimated_duration_seconds: Optional[float] = None
    output_width: Optional[int] = None
    output_height: Optional[int] = None
    output_fps: Optional[float] = None
    fit: str
    cover_region_count: int
    text_overlay_count: int
    ai_asset_slot_count: int = 0
    selected_ai_asset_count: int = 0
    ai_asset_slots: List[Dict[str, Any]] = Field(default_factory=list)
    playback_speed: Optional[float] = None
    mute_audio: bool
    music_track_id: Optional[int] = None
    music_title: Optional[str] = None
    music_mode: Optional[str] = None
    music_volume: Optional[float] = None
    music_loop: bool = False
    warnings: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)


class VariantPreflightRead(BaseModel):
    asset_id: int
    asset_filename: str
    asset_duration_seconds: Optional[float] = None
    items: List[VariantPreflightItem]


class ProductionRunPreflightRequest(BaseModel):
    asset_ids: List[int]
    template_ids: List[int]
    runtime_values: Dict[str, Any] = Field(default_factory=dict)
    output_preset_id: Optional[str] = None
    name_prefix: str = "production-batch"


class ProductionRunPreflightSummary(BaseModel):
    asset_count: int
    template_count: int
    task_count: int
    ready_count: int
    warning_count: int
    blocked_count: int


class ProductionRunPreflightRead(BaseModel):
    preflight_token: str
    summary: ProductionRunPreflightSummary
    items: List[VariantPreflightItem]
    runtime_values: Dict[str, Any] = Field(default_factory=dict)
    output_preset_id: Optional[str] = None
    name_prefix: str


class ProductionRunEnqueueRequest(ProductionRunPreflightRequest):
    preflight_token: Optional[str] = None


class TaskRunRequest(BaseModel):
    segment_seconds: Optional[float] = None


class RenderPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    plan_json: Dict[str, Any]
    status: str


class OutputVideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    render_plan_id: int
    filename: str
    file_path: str
    status: str
    review_status: str
    review_notes: Optional[str] = None
    review_feedback_json: Optional[Dict[str, Any]] = None


class ReviewChangeRequest(BaseModel):
    category: str
    request: str
    target: Optional[str] = None
    priority: Optional[str] = None


class OutputReviewUpdate(BaseModel):
    review_status: str
    review_notes: Optional[str] = None
    reviewer_name: Optional[str] = None
    change_request: Optional[str] = None
    change_requests: List[ReviewChangeRequest] = Field(default_factory=list)
    priority: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ProductionRunStatusUpdate(BaseModel):
    status: str


class ProductionRunPackageEstimate(BaseModel):
    production_run_id: int
    package_name: str
    seed_filename: str
    seed_size_bytes: int
    approved_output_count: int
    approved_output_size_bytes: int
    total_size_bytes: int
    missing_files: List[str] = Field(default_factory=list)


class OutputReviewRead(BaseModel):
    output_id: int
    asset_id: int
    asset_filename: str
    production_run_id: Optional[int] = None
    production_run_name: Optional[str] = None
    production_run_status: Optional[str] = None
    revision_number: int = 1
    task_id: int
    task_name: str
    template_id: int
    template_name: str
    template_version: int
    render_plan_id: int
    creative_goal: Dict[str, Any] = Field(default_factory=dict)
    production_contract: Dict[str, Any] = Field(default_factory=dict)
    render_plan: Dict[str, Any] = Field(default_factory=dict)
    file_path: str
    duration_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    status: str
    review_status: str
    review_notes: Optional[str] = None
    review_feedback: Optional[Dict[str, Any]] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class TaskRunResponse(BaseModel):
    task: GenerationTaskRead
    segments: List[SegmentRead]
    render_plan: RenderPlanRead
    output: OutputVideoRead
