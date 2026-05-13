from datetime import datetime
from typing import Any, Dict, List, Optional, Union

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


class AuthRegisterRequest(BaseModel):
    phone: str
    password: str
    display_name: Optional[str] = None


class AuthLoginRequest(BaseModel):
    phone: str
    password: str


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
    safe_area_top: int = Field(default=0, ge=0, le=2000)
    safe_area_bottom: int = Field(default=0, ge=0, le=2000)

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
    x: Union[int, str] = 0
    y: Union[int, str] = 0
    font_size: int = Field(default=54, ge=12, le=180)
    font_color: str = "white"
    box_color: Optional[str] = "black@0.62"
    box_padding: int = Field(default=18, ge=0, le=80)

    @field_validator("x", "y")
    @classmethod
    def validate_position(cls, value: Union[int, str]) -> Union[int, str]:
        if isinstance(value, int):
            if value < 0:
                raise ValueError("position must be non-negative")
            return value
        if isinstance(value, str) and value.strip():
            return value.strip()
        raise ValueError("position must be a non-negative int or an ffmpeg expression string")


class TemplateTransformationsSpec(BaseModel):
    brightness: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    contrast: Optional[float] = Field(default=None, ge=0.0, le=3.0)
    saturation: Optional[float] = Field(default=None, ge=0.0, le=3.0)
    playback_speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    volume: Optional[float] = Field(default=None, ge=0.0, le=3.0)
    mute_audio: bool = False
    cover_regions: List[TemplateCoverRegion] = Field(default_factory=list)
    text_overlays: List[TemplateTextOverlay] = Field(default_factory=list)


class TemplateCreativeGoal(BaseModel):
    title: Optional[str] = None
    audience: Optional[str] = None
    selling_points: List[str] = Field(default_factory=list)
    tone: Optional[str] = None


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
    safe_area_top: int = Field(default=0, ge=0, le=2000)
    safe_area_bottom: int = Field(default=0, ge=0, le=2000)

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
        if self.height is not None and (self.safe_area_top + self.safe_area_bottom) >= self.height:
            raise ValueError(
                "delivery.safe_area_top + safe_area_bottom must leave room for content"
            )
        return self


class TemplateCardSpec(BaseModel):
    """Full-screen intro or outro text card spliced before/after the seed video."""

    enabled: bool = False
    text: str = ""
    subtitle: Optional[str] = None
    duration_seconds: float = Field(default=1.5, gt=0, le=5.0)
    background_color: str = "black"
    font_color: str = "white"
    font_size: int = Field(default=72, ge=12, le=240)
    subtitle_font_color: str = "white"
    subtitle_font_size: int = Field(default=40, ge=12, le=200)

    @model_validator(mode="after")
    def validate_text_when_enabled(self) -> "TemplateCardSpec":
        if self.enabled and not self.text.strip():
            raise ValueError("card text cannot be empty when the card is enabled")
        return self


class TemplateSubtitleBarSpec(BaseModel):
    """Persistent text bar overlaid on the seed video frames."""

    enabled: bool = False
    text: str = ""
    position: str = "bottom"
    font_size: int = Field(default=48, ge=12, le=160)
    font_color: str = "white"
    bar_color: str = "black@0.6"
    bar_height: int = Field(default=140, ge=20, le=600)
    horizontal_padding: int = Field(default=60, ge=0, le=600)

    @field_validator("position")
    @classmethod
    def validate_position(cls, value: str) -> str:
        if value not in {"top", "bottom", "center"}:
            raise ValueError("subtitle_bar.position must be top, bottom, or center")
        return value

    @model_validator(mode="after")
    def validate_text_when_enabled(self) -> "TemplateSubtitleBarSpec":
        if self.enabled and not self.text.strip():
            raise ValueError("subtitle_bar.text cannot be empty when enabled")
        return self


class TemplateSpec(BaseModel):
    type: str = "concat"
    creative_goal: TemplateCreativeGoal = Field(default_factory=TemplateCreativeGoal)
    editing: Optional[TemplateEditingSpec] = None
    delivery: Optional[TemplateDeliverySpec] = None
    review_notes: Optional[str] = None
    output: TemplateOutputSpec = Field(default_factory=TemplateOutputSpec)
    selection: TemplateSelectionSpec = Field(default_factory=TemplateSelectionSpec)
    segments: TemplateSegmentsSpec = Field(default_factory=TemplateSegmentsSpec)
    layout: TemplateLayoutSpec = Field(default_factory=TemplateLayoutSpec)
    transformations: TemplateTransformationsSpec = Field(
        default_factory=TemplateTransformationsSpec
    )
    intro_card: Optional[TemplateCardSpec] = None
    subtitle_bar: Optional[TemplateSubtitleBarSpec] = None
    outro_card: Optional[TemplateCardSpec] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value != "concat":
            raise ValueError("Only concat templates are supported by the MVP renderer")
        return value


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    version: int = 1
    json_spec: TemplateSpec
    is_builtin: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[int] = None
    json_spec: Optional[TemplateSpec] = None
    is_builtin: Optional[bool] = None


class TemplateValidationRequest(BaseModel):
    json_spec: TemplateSpec


class TemplateValidationRead(BaseModel):
    valid: bool
    normalized_spec: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)


class GenerationTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
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
    params_json: Optional[Dict[str, Any]] = None


class RenderVariantsRequest(BaseModel):
    name_prefix: str
    template_ids: List[int]
    params_json: Optional[Dict[str, Any]] = None


class VariantPreflightItem(BaseModel):
    template_id: int
    template_name: str
    title: Optional[str] = None
    estimated_clip_count: int
    estimated_duration_seconds: Optional[float] = None
    output_width: Optional[int] = None
    output_height: Optional[int] = None
    output_fps: Optional[float] = None
    fit: str
    cover_region_count: int
    text_overlay_count: int
    playback_speed: Optional[float] = None
    mute_audio: bool
    warnings: List[str] = Field(default_factory=list)


class VariantPreflightRead(BaseModel):
    asset_id: int
    asset_filename: str
    asset_duration_seconds: Optional[float] = None
    items: List[VariantPreflightItem]


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


class OutputReviewUpdate(BaseModel):
    review_status: str
    review_notes: Optional[str] = None
    reviewer_name: Optional[str] = None
    change_request: Optional[str] = None
    priority: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class OutputReviewRead(BaseModel):
    output_id: int
    asset_id: int
    asset_filename: str
    task_id: int
    task_name: str
    template_id: int
    template_name: str
    template_version: int
    render_plan_id: int
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
