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


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


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


class GenerationTask(TimestampMixin, Base):
    __tablename__ = "generation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
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
