from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AssetStatus(str, Enum):
    UPLOADED = "uploaded"
    PROBING = "probing"
    READY = "ready"
    FAILED = "failed"


class SegmentStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    WAITING = "waiting"
    SEGMENTING = "segmenting"
    PLANNING = "planning"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RenderPlanStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RENDERING = "rendering"
    RENDERED = "rendered"
    FAILED = "failed"


class OutputVideoStatus(str, Enum):
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CHANGES = "needs_changes"
    DISCARDED = "discarded"


class ProductionRunStatus(str, Enum):
    IN_REVIEW = "in_review"
    NEEDS_REVISION = "needs_revision"
    APPROVED = "approved"
    ARCHIVED = "archived"


class AIAssetKind(str, Enum):
    VIDEO = "video"
    IMAGE = "image"


class AIAssetType(str, Enum):
    HOOK = "hook"
    CTA = "cta"
    BROLL = "broll"
    REACTION = "reaction"
    MEME = "meme"
    PRODUCT_MOTION = "product_motion"


class AIAssetStatus(str, Enum):
    IMPORTING = "importing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class AICloneJobStatus(str, Enum):
    QUEUED = "queued"
    PRECHECKING = "prechecking"
    STARTING_WORKER = "starting_worker"
    WARMING_MODELS = "warming_models"
    SUBMITTING = "submitting"
    WAITING_PROVIDER = "waiting_provider"
    RUNNING = "running"
    POSTPROCESSING = "postprocessing"
    IMPORTING = "importing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class AICloneWorkerStatus(str, Enum):
    STARTING = "starting"
    WARMING_MODELS = "warming_models"
    READY = "ready"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


class CreativeReferenceRightsStatus(str, Enum):
    REFERENCE_ONLY = "reference_only"
    NEEDS_REVIEW = "needs_review"
    LICENSED = "licensed"
    OWNED = "owned"
    PUBLIC_DOMAIN = "public_domain"
    CC_BY = "cc_by"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    music_tracks: Mapped[List["MusicTrack"]] = relationship(back_populates="user")
    ai_assets: Mapped[List["AIAsset"]] = relationship(back_populates="user")


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    fps: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default=AssetStatus.UPLOADED.value)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    segments: Mapped[List["Segment"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    generation_tasks: Mapped[List["GenerationTask"]] = relationship(back_populates="asset")
    production_runs: Mapped[List["ProductionRun"]] = relationship(back_populates="asset")


class Segment(TimestampMixin, Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024))
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(1024))
    detection_method: Mapped[Optional[str]] = mapped_column(String(64))
    scene_score: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default=SegmentStatus.PENDING.value)

    asset: Mapped[Asset] = relationship(back_populates="segments")


class Template(TimestampMixin, Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    json_spec: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)

    generation_tasks: Mapped[List["GenerationTask"]] = relationship(
        back_populates="template"
    )


class CreativeReference(TimestampMixin, Base):
    __tablename__ = "creative_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    source_site: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048))
    rights_status: Mapped[str] = mapped_column(
        String(32), default=CreativeReferenceRightsStatus.REFERENCE_ONLY.value
    )
    component_type: Mapped[str] = mapped_column(String(64), default="layout_reference")
    industry: Mapped[Optional[str]] = mapped_column(String(120))
    style_tags: Mapped[list] = mapped_column(JSON, default=list)
    layout_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MusicTrack(TimestampMixin, Base):
    __tablename__ = "music_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    scope: Mapped[str] = mapped_column(String(32), default="private")
    artist: Mapped[Optional[str]] = mapped_column(String(255))
    license_name: Mapped[Optional[str]] = mapped_column(String(120))
    license_url: Mapped[Optional[str]] = mapped_column(String(1024))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    attribution_text: Mapped[Optional[str]] = mapped_column(Text)
    mood: Mapped[Optional[str]] = mapped_column(String(120))
    bpm: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[Optional[User]] = relationship(back_populates="music_tracks")


class AIAsset(TimestampMixin, Base):
    __tablename__ = "ai_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(32), default="private")
    provider: Mapped[str] = mapped_column(String(64), default="manual")
    asset_kind: Mapped[str] = mapped_column(String(32), default=AIAssetKind.VIDEO.value)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[Optional[str]] = mapped_column(Text)
    source_image_path: Mapped[Optional[str]] = mapped_column(String(1024))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    fps: Mapped[Optional[float]] = mapped_column(Float)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(1024))
    generation_cost: Mapped[Optional[float]] = mapped_column(Float)
    generation_time_seconds: Mapped[Optional[float]] = mapped_column(Float)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    roi_score: Mapped[Optional[float]] = mapped_column(Float)
    avg_ctr_lift: Mapped[Optional[float]] = mapped_column(Float)
    review_reject_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default=AIAssetStatus.IMPORTING.value)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped[Optional[User]] = relationship(back_populates="ai_assets")
    tags: Mapped[List["AIAssetTag"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class AIAssetTag(TimestampMixin, Base):
    __tablename__ = "ai_asset_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("ai_assets.id"), nullable=False)
    tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    asset: Mapped[AIAsset] = relationship(back_populates="tags")


class AICloneWorkflow(TimestampMixin, Base):
    __tablename__ = "ai_clone_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="mock")
    endpoint_ref: Mapped[Optional[str]] = mapped_column(String(255))
    manifest_json: Mapped[dict] = mapped_column(JSON, default=dict)
    workflow_api_json: Mapped[dict] = mapped_column(JSON, default=dict)
    params_schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="active")
    estimated_credits: Mapped[int] = mapped_column(Integer, default=0)
    estimated_seconds: Mapped[Optional[int]] = mapped_column(Integer)


class AICloneWorker(TimestampMixin, Base):
    __tablename__ = "ai_clone_workers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), default="mock")
    cloud_region: Mapped[Optional[str]] = mapped_column(String(120))
    gpu_type: Mapped[Optional[str]] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32), default=AICloneWorkerStatus.STOPPED.value)
    endpoint_url_secret_ref: Mapped[Optional[str]] = mapped_column(String(255))
    current_job_id: Mapped[Optional[int]] = mapped_column(Integer)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    idle_since: Mapped[Optional[datetime]] = mapped_column(DateTime)
    cost_per_second_estimate: Mapped[Optional[float]] = mapped_column(Float)


class AICloneJob(TimestampMixin, Base):
    __tablename__ = "ai_clone_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="mock")
    provider_job_id: Mapped[Optional[str]] = mapped_column(String(255))
    worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ai_clone_workers.id"))
    reference_asset_id: Mapped[Optional[int]] = mapped_column(Integer)
    reference_asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    reference_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    input_params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=AICloneJobStatus.QUEUED.value)
    estimated_credits: Mapped[int] = mapped_column(Integer, default=0)
    actual_credits: Mapped[Optional[int]] = mapped_column(Integer)
    output_asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ai_assets.id"))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    queue_position: Mapped[Optional[int]] = mapped_column(Integer)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[Optional[str]] = mapped_column(String(255))
    estimated_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    wait_seconds: Mapped[Optional[float]] = mapped_column(Float)
    elapsed_seconds: Mapped[Optional[float]] = mapped_column(Float)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    simulated_queue_ahead: Mapped[int] = mapped_column(Integer, default=0)
    queue_entered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    provider_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    postprocess_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class AICloneJobEvent(TimestampMixin, Base):
    __tablename__ = "ai_clone_job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("ai_clone_jobs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[Optional[str]] = mapped_column(String(255))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    raw_response_json: Mapped[Optional[dict]] = mapped_column(JSON)


class ProductionRun(TimestampMixin, Base):
    __tablename__ = "production_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_prefix: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ProductionRunStatus.IN_REVIEW.value)

    asset: Mapped[Asset] = relationship(back_populates="production_runs")
    generation_tasks: Mapped[List["GenerationTask"]] = relationship(
        back_populates="production_run"
    )


class GenerationTask(TimestampMixin, Base):
    __tablename__ = "generation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    production_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("production_runs.id"), nullable=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.QUEUED.value)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[Optional[str]] = mapped_column(String(255))
    params_json: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    asset: Mapped[Asset] = relationship(back_populates="generation_tasks")
    production_run: Mapped[Optional[ProductionRun]] = relationship(
        back_populates="generation_tasks"
    )
    template: Mapped[Template] = relationship(back_populates="generation_tasks")
    render_plan: Mapped[Optional["RenderPlan"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", uselist=False
    )
    output_videos: Mapped[List["OutputVideo"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    events: Mapped[List["TaskEvent"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class TaskEvent(TimestampMixin, Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("generation_tasks.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[Optional[str]] = mapped_column(String(255))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    task: Mapped[GenerationTask] = relationship(back_populates="events")


class RenderPlan(TimestampMixin, Base):
    __tablename__ = "render_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("generation_tasks.id"), nullable=False, unique=True
    )
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=RenderPlanStatus.DRAFT.value)

    task: Mapped[GenerationTask] = relationship(back_populates="render_plan")
    output_videos: Mapped[List["OutputVideo"]] = relationship(
        back_populates="render_plan"
    )


class OutputVideo(TimestampMixin, Base):
    __tablename__ = "output_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("generation_tasks.id"), nullable=False)
    render_plan_id: Mapped[int] = mapped_column(
        ForeignKey("render_plans.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    fps: Mapped[Optional[float]] = mapped_column(Float)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default=OutputVideoStatus.RENDERING.value)
    review_status: Mapped[str] = mapped_column(
        String(32), default=ReviewStatus.PENDING_REVIEW.value
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    review_feedback_json: Mapped[Optional[dict]] = mapped_column(JSON)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    task: Mapped[GenerationTask] = relationship(back_populates="output_videos")
    render_plan: Mapped[RenderPlan] = relationship(back_populates="output_videos")
