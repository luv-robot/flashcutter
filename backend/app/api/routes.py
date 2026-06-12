import hashlib
import csv
import io
import json
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import (
    AIAsset,
    AIAssetKind,
    AIAssetStatus,
    AIAssetTag,
    AIAssetType,
    AICloneJob,
    AICloneJobEvent,
    AICloneJobStatus,
    AICloneWorkflow,
    AICloneWorker,
    AICloneWorkerStatus,
    Asset,
    AssetStatus,
    CreativeReference,
    GenerationTask,
    MusicTrack,
    OutputVideo,
    OutputVideoStatus,
    ProductionRun,
    ProductionRunStatus,
    RenderPlan,
    RenderPlanStatus,
    ReviewStatus,
    Segment,
    SegmentStatus,
    TaskEvent,
    TaskStatus,
    Template,
    User,
)
from app.schemas import (
    AIAssetRead,
    AIAssetUpdate,
    AICloneJobEventRead,
    AICloneJobRead,
    AICloneWorkflowRead,
    AssetRead,
    AssetImportUrl,
    AuthLoginRequest,
    AuthPasswordChangeRequest,
    AuthRegisterRequest,
    AuthResponse,
    AuthUserRead,
    CreativeReferenceCreate,
    CreativeReferenceImportRequest,
    CreativeReferenceRead,
    GenerationTaskBatchCreate,
    GenerationTaskCreate,
    GenerationTaskRead,
    MusicTrackRead,
    OpeningCopySuggestion,
    OutputVideoRead,
    OutputReviewRead,
    OutputReviewUpdate,
    ProductionRunPackageEstimate,
    ProductionRunEnqueueRequest,
    ProductionRunPreflightRead,
    ProductionRunPreflightRequest,
    ProductionRunPreflightSummary,
    ProductionRunStatusUpdate,
    RenderVariantsRequest,
    RenderPlanRead,
    SegmentRead,
    StrongOpeningCopyRequest,
    StrongOpeningCopyResponse,
    StrongOpeningExpansionEnqueueRequest,
    StrongOpeningExpansionPreflightRead,
    StrongOpeningExpansionRequest,
    TaskRunRequest,
    TaskRunResponse,
    TaskEventRead,
    TemplateCreate,
    TemplateRead,
    CompiledTemplateSpec,
    TemplateSpec,
    TemplateSpecV3,
    TemplateUpdate,
    TemplateValidationRead,
    TemplateValidationRequest,
    TextRegionDetectionRead,
    VariantPreflightItem,
    VariantPreflightRead,
)
from app.services.opening_copy import opening_copy_suggestions, suggestion_id, trim_copy
from app.services.template_compiler import (
    compile_template_spec,
    template_warnings,
)
from app.services.template_v3_compiler import (
    compile_template_v3_spec,
    v3_missing_runtime_fields,
    v3_operation_labels,
    v3_runtime_asset_ids,
)
from app.services.creative_reference_importer import importable_metadata_for_url
from app.services.ffmpeg import (
    FFmpegError,
    extract_video_frame,
    probe_media,
    render_image_motion_clip,
    render_concat,
    replace_audio_track,
    render_timeline,
    split_fixed_segments,
)
from app.services.comfyui_client import ComfyUIClient, ComfyUIError, workflow_with_bindings
from app.services.auth import (
    create_session,
    ensure_unique_phone,
    hash_password,
    normalize_phone,
    token_from_request,
    user_for_token,
    verify_password,
)
from app.services.storage import (
    ai_asset_generated_video_path,
    ai_asset_source_image_path,
    ai_asset_upload_path,
    ai_clone_conditioning_image_path,
    ai_clone_output_path,
    ai_clone_reference_path,
    asset_segments_dir,
    asset_analysis_dir,
    asset_upload_path,
    concat_list_path,
    filename_from_url,
    music_upload_path,
    save_upload_file,
    storage_root,
    task_output_path,
)
from app.services.task_queue import task_queue
from app.services.text_detection import detect_text_regions
from app.template_library import STRONG_OPENING_TEMPLATE_NAME

router = APIRouter(prefix="/api")
settings = get_settings()


def auth_response_for_user(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_session(user),
        user=AuthUserRead(
            id=user.id,
            phone=user.phone,
            display_name=user.display_name,
        ),
    )


@router.post("/auth/register", response_model=AuthResponse)
def register_user(
    payload: AuthRegisterRequest, db: Session = Depends(get_db)
) -> AuthResponse:
    from app.config import get_settings

    if not get_settings().allow_registration:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    phone = normalize_phone(payload.phone)
    ensure_unique_phone(db, phone)
    user = User(
        phone=phone,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return auth_response_for_user(user)


@router.post("/auth/login", response_model=AuthResponse)
def login_user(payload: AuthLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    phone = normalize_phone(payload.phone)
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone number or password")
    return auth_response_for_user(user)


@router.get("/auth/me", response_model=AuthUserRead)
def read_current_user(request: Request, db: Session = Depends(get_db)) -> AuthUserRead:
    token = token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = user_for_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return AuthUserRead(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
    )


@router.patch("/auth/password", response_model=AuthUserRead)
def change_password(
    payload: AuthPasswordChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthUserRead:
    user = current_user_from_request(request, db)
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    return AuthUserRead(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
    )


def optional_user_from_request(request: Request, db: Session) -> Optional[User]:
    token = token_from_request(request)
    if not token:
        return None
    return user_for_token(db, token)


def current_user_from_request(request: Request, db: Session) -> User:
    token = token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = user_for_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def ensure_task_access(task: GenerationTask, request: Request, db: Session) -> Optional[User]:
    user = optional_user_from_request(request, db)
    if user is not None and task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return user


def ensure_output_access(output: OutputVideo, request: Request, db: Session) -> Optional[User]:
    user = optional_user_from_request(request, db)
    if user is not None and output.task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Output video not found")
    return user


def ensure_production_run_access(
    production_run: ProductionRun, request: Request, db: Session
) -> Optional[User]:
    user = optional_user_from_request(request, db)
    if user is None:
        return None
    owns_run = db.scalar(
        select(GenerationTask.id)
        .where(GenerationTask.production_run_id == production_run.id)
        .where(GenerationTask.user_id == user.id)
    )
    if owns_run is None:
        raise HTTPException(status_code=404, detail="Production run not found")
    return user


def normalize_ai_asset_tags(tags: Optional[List[str]]) -> List[str]:
    normalized = []
    seen = set()
    for tag in tags or []:
        value = tag.strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value[:64])
    return normalized


def ai_asset_kind_for_upload(file: UploadFile) -> str:
    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    if content_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return AIAssetKind.IMAGE.value
    if content_type.startswith("video/") or suffix in {".mp4", ".mov", ".m4v", ".webm"}:
        return AIAssetKind.VIDEO.value
    raise HTTPException(status_code=400, detail="AI asset must be an image or video file")


def ensure_image_upload(file: UploadFile) -> None:
    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    if content_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return
    raise HTTPException(status_code=400, detail="AI generation source must be an image")


def ai_clone_reference_type_for_upload(file: UploadFile) -> str:
    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    if content_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return "image"
    if content_type.startswith("video/") or suffix in {".mp4", ".mov", ".m4v", ".webm"}:
        return "video"
    raise HTTPException(status_code=400, detail="参考素材必须是图片或视频文件")


AI_CLONE_WORKFLOW_MANIFESTS = [
    {
        "workflow_id": "image_clone_video_v1",
        "version": "0.1.0",
        "name": "原图仿制视频",
        "mode": "image_to_video",
        "provider": "mock",
        "status": "active",
        "estimated_credits": 8,
        "estimated_seconds": 90,
        "params_schema_json": {
            "type": "object",
            "required": ["prompt", "duration"],
            "properties": {
                "prompt": {"type": "string", "title": "仿制目标", "maxLength": 240},
                "negative_prompt": {"type": "string", "title": "排除内容", "maxLength": 240},
                "duration": {"type": "number", "title": "时长", "minimum": 2, "maximum": 8},
                "similarity": {"type": "number", "title": "相似度", "minimum": 0, "maximum": 1},
                "motion_strength": {"type": "number", "title": "运动强度", "minimum": 0, "maximum": 1},
            },
        },
        "manifest_json": {"default_tags": ["clone", "image_to_video"]},
        "workflow_api_json": {"mock": True},
    },
    {
        "workflow_id": "video_clone_clip_v1",
        "version": "0.1.0",
        "name": "原视频仿制片段",
        "mode": "video_to_video",
        "provider": "mock",
        "status": "active",
        "estimated_credits": 12,
        "estimated_seconds": 150,
        "params_schema_json": {
            "type": "object",
            "required": ["prompt", "duration"],
            "properties": {
                "prompt": {"type": "string", "title": "仿制目标", "maxLength": 240},
                "negative_prompt": {"type": "string", "title": "排除内容", "maxLength": 240},
                "duration": {"type": "number", "title": "时长", "minimum": 2, "maximum": 8},
                "similarity": {"type": "number", "title": "相似度", "minimum": 0, "maximum": 1},
                "motion_strength": {"type": "number", "title": "运动强度", "minimum": 0, "maximum": 1},
            },
        },
        "manifest_json": {"default_tags": ["clone", "video_to_video"]},
        "workflow_api_json": {"mock": True},
    },
]


def load_ai_clone_workflow_json(path_value: str) -> Dict[str, Any]:
    if not path_value:
        return {}
    path = resolve_project_path(path_value)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_ai_clone_workflow_manifest(path_value: str) -> Dict[str, Any]:
    if not path_value:
        return {}
    path = resolve_project_path(path_value)
    manifest_path = path.parent / "manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    repo_path = Path.cwd().parent / path
    if repo_path.exists():
        return repo_path
    return cwd_path


def ai_clone_manifest_for_settings(manifest: Dict[str, Any]) -> Dict[str, Any]:
    configured = dict(manifest)
    provider = settings.ai_clone_provider if settings.ai_clone_provider in {"mock", "comfyui"} else "mock"
    configured["provider"] = provider
    configured["endpoint_ref"] = (
        "FLASHCUTTER_COMFYUI_BASE_URL" if provider == "comfyui" else None
    )
    workflow_path = (
        settings.ai_clone_image_workflow_path
        if manifest["mode"] == "image_to_video"
        else settings.ai_clone_video_workflow_path
    )
    workflow_json = load_ai_clone_workflow_json(workflow_path)
    workflow_manifest = load_ai_clone_workflow_manifest(workflow_path)
    bindings = workflow_manifest.get("bindings") or default_comfyui_workflow_bindings()
    if workflow_json:
        configured["workflow_api_json"] = workflow_json
        configured["manifest_json"] = {
            **manifest.get("manifest_json", {}),
            "workflow_path": workflow_path,
            "bindings": bindings,
        }
    elif provider == "comfyui":
        configured["workflow_api_json"] = {}
        configured["manifest_json"] = {
            **manifest.get("manifest_json", {}),
            "bindings": bindings,
            "configuration_warning": "ComfyUI provider is enabled but workflow JSON path is not configured",
        }
    return configured


def default_comfyui_workflow_bindings() -> Dict[str, List[str]]:
    return {
        "prompt": ["6", "inputs", "text"],
        "negative_prompt": ["7", "inputs", "text"],
        "reference_file": ["10", "inputs", "image"],
    }


def seed_ai_clone_workflows(db: Session) -> None:
    for raw_manifest in AI_CLONE_WORKFLOW_MANIFESTS:
        manifest = ai_clone_manifest_for_settings(raw_manifest)
        workflow = db.scalar(
            select(AICloneWorkflow).where(
                AICloneWorkflow.workflow_id == manifest["workflow_id"]
            )
        )
        if workflow is None:
            workflow = AICloneWorkflow(
                workflow_id=manifest["workflow_id"],
                version=manifest["version"],
                name=manifest["name"],
                mode=manifest["mode"],
                provider=manifest["provider"],
                endpoint_ref=manifest.get("endpoint_ref"),
                status=manifest["status"],
                estimated_credits=manifest["estimated_credits"],
                estimated_seconds=manifest["estimated_seconds"],
                params_schema_json=manifest["params_schema_json"],
                manifest_json=manifest["manifest_json"],
                workflow_api_json=manifest["workflow_api_json"],
            )
            db.add(workflow)
            continue
        workflow.version = manifest["version"]
        workflow.name = manifest["name"]
        workflow.mode = manifest["mode"]
        workflow.provider = manifest["provider"]
        workflow.endpoint_ref = manifest.get("endpoint_ref")
        workflow.status = manifest["status"]
        workflow.estimated_credits = manifest["estimated_credits"]
        workflow.estimated_seconds = manifest["estimated_seconds"]
        workflow.params_schema_json = manifest["params_schema_json"]
        workflow.manifest_json = manifest["manifest_json"]
        workflow.workflow_api_json = manifest["workflow_api_json"]
    db.commit()


def ensure_ai_asset_visible(asset: AIAsset, user: User) -> None:
    if asset.scope == "system":
        return
    if asset.user_id != user.id:
        raise HTTPException(status_code=404, detail="AI asset not found")


def set_ai_asset_tags(db: Session, asset: AIAsset, tags: Optional[List[str]]) -> None:
    asset.tags.clear()
    for tag in normalize_ai_asset_tags(tags):
        asset.tags.append(AIAssetTag(tag=tag))


def create_ai_clone_event(
    db: Session,
    job: AICloneJob,
    status: str,
    progress_percent: Optional[int] = None,
    message: Optional[str] = None,
    error_message: Optional[str] = None,
    raw_response_json: Optional[dict] = None,
) -> None:
    if progress_percent is not None:
        job.progress_percent = progress_percent
    job.status = status
    job.progress_message = message
    job.error_message = error_message
    job.last_heartbeat_at = datetime.utcnow()
    db.add(
        AICloneJobEvent(
            job_id=job.id,
            status=status,
            progress_percent=job.progress_percent,
            message=message,
            error_message=error_message,
            raw_response_json=raw_response_json,
        )
    )


def refresh_ai_clone_queue_positions(db: Session, user_id: Optional[int] = None) -> None:
    query = select(AICloneJob).where(AICloneJob.status == AICloneJobStatus.QUEUED.value)
    if user_id is not None:
        query = query.where(AICloneJob.user_id == user_id)
    jobs = list(db.scalars(query.order_by(AICloneJob.queue_entered_at.asc(), AICloneJob.id.asc())))
    for index, job in enumerate(jobs, start=1):
        job.queue_position = index


def enqueue_ai_clone_job(job_id: int, provider: str) -> None:
    runner = run_comfyui_ai_clone_job if provider == "comfyui" else run_mock_ai_clone_job
    task_queue.enqueue(job_id, runner)


def parse_tag_text(tags: Optional[str]) -> List[str]:
    if not tags:
        return []
    return [tag.strip() for tag in tags.split(",") if tag.strip()]


def ai_clone_workflow_for_id(db: Session, workflow_id: str) -> AICloneWorkflow:
    seed_ai_clone_workflows(db)
    workflow = db.scalar(
        select(AICloneWorkflow).where(AICloneWorkflow.workflow_id == workflow_id)
    )
    if workflow is None or workflow.status != "active":
        raise HTTPException(status_code=404, detail="仿制 workflow 不可用")
    return workflow


@router.get("/ai-assets", response_model=List[AIAssetRead])
def list_ai_assets(
    request: Request,
    db: Session = Depends(get_db),
    asset_type: Optional[str] = Query(default=None),
    asset_kind: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    scope: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    status: str = Query(default=AIAssetStatus.READY.value),
) -> List[AIAssetRead]:
    user = current_user_from_request(request, db)
    query = select(AIAsset).where(
        ((AIAsset.scope == "system") | (AIAsset.user_id == user.id))
    )
    if asset_type:
        query = query.where(AIAsset.asset_type == asset_type)
    if asset_kind:
        query = query.where(AIAsset.asset_kind == asset_kind)
    if provider:
        query = query.where(AIAsset.provider == provider)
    if scope:
        query = query.where(AIAsset.scope == scope)
    if status:
        query = query.where(AIAsset.status == status)
    if tag:
        query = query.join(AIAsset.tags).where(AIAssetTag.tag == tag.strip().lower())
    return list(db.scalars(query.order_by(AIAsset.created_at.desc())).unique())


@router.post("/ai-assets/upload", response_model=AIAssetRead)
async def upload_ai_asset(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    asset_type: str = Form(default=AIAssetType.HOOK.value),
    prompt: Optional[str] = Form(default=None),
    provider: str = Form(default="manual"),
    tags: Optional[str] = Form(default=None),
    scope: str = Form(default="private"),
    db: Session = Depends(get_db),
) -> AIAssetRead:
    user = current_user_from_request(request, db)
    if asset_type not in {item.value for item in AIAssetType}:
        raise HTTPException(status_code=400, detail="Unsupported AI asset type")
    if scope not in {"private", "system"}:
        raise HTTPException(status_code=400, detail="scope must be private or system")

    asset_kind = ai_asset_kind_for_upload(file)
    original_filename = file.filename or f"ai-asset.{asset_kind}"
    asset = AIAsset(
        user_id=None if scope == "system" else user.id,
        scope=scope,
        provider=provider or "manual",
        asset_kind=asset_kind,
        asset_type=asset_type,
        title=title or Path(original_filename).stem,
        prompt=prompt,
        original_filename=original_filename,
        stored_filename="",
        file_path="",
        mime_type=file.content_type,
        status=AIAssetStatus.IMPORTING.value,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    destination = ai_asset_upload_path(asset.id, original_filename)
    file_size = await save_upload_file(file, destination)
    asset.stored_filename = destination.name
    asset.file_path = str(destination)
    asset.file_size_bytes = file_size
    if asset.asset_kind == AIAssetKind.VIDEO.value:
        try:
            metadata = probe_media(destination)
            asset.duration_seconds = metadata.get("duration_seconds")
            asset.width = metadata.get("width")
            asset.height = metadata.get("height")
            asset.fps = metadata.get("fps")
            asset.status = AIAssetStatus.READY.value
        except FFmpegError as exc:
            asset.status = AIAssetStatus.FAILED.value
            asset.error_message = str(exc)
    else:
        asset.status = AIAssetStatus.READY.value
    tag_values = tags.split(",") if tags else []
    set_ai_asset_tags(db, asset, tag_values)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/ai-assets/{asset_id}", response_model=AIAssetRead)
def get_ai_asset(
    asset_id: int, request: Request, db: Session = Depends(get_db)
) -> AIAssetRead:
    user = current_user_from_request(request, db)
    asset = db.get(AIAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="AI asset not found")
    ensure_ai_asset_visible(asset, user)
    return asset


@router.post("/ai-assets/generate/local-motion", response_model=AIAssetRead)
async def generate_local_motion_ai_asset(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    asset_type: str = Form(default=AIAssetType.HOOK.value),
    prompt: Optional[str] = Form(default=None),
    tags: Optional[str] = Form(default=None),
    duration_seconds: float = Form(default=3.0),
    width: int = Form(default=1080),
    height: int = Form(default=1920),
    fps: float = Form(default=30.0),
    db: Session = Depends(get_db),
) -> AIAssetRead:
    user = current_user_from_request(request, db)
    ensure_image_upload(file)
    if asset_type not in {item.value for item in AIAssetType}:
        raise HTTPException(status_code=400, detail="Unsupported AI asset type")
    if duration_seconds <= 0 or duration_seconds > 10:
        raise HTTPException(status_code=400, detail="duration_seconds must be between 0 and 10")
    if width <= 0 or height <= 0 or width % 2 != 0 or height % 2 != 0:
        raise HTTPException(status_code=400, detail="width and height must be positive even numbers")
    if fps <= 0 or fps > 60:
        raise HTTPException(status_code=400, detail="fps must be between 0 and 60")

    original_filename = file.filename or "source-image.png"
    asset = AIAsset(
        user_id=user.id,
        scope="private",
        provider="local_motion_mvp",
        asset_kind=AIAssetKind.VIDEO.value,
        asset_type=asset_type,
        title=title or Path(original_filename).stem,
        prompt=prompt,
        original_filename=f"{Path(original_filename).stem}-generated.mp4",
        stored_filename="",
        file_path="",
        mime_type="video/mp4",
        status=AIAssetStatus.IMPORTING.value,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    source_path = ai_asset_source_image_path(asset.id, original_filename)
    output_path = ai_asset_generated_video_path(asset.id)
    await save_upload_file(file, source_path)
    asset.source_image_path = str(source_path)
    try:
        render_image_motion_clip(
            image_path=source_path,
            output_path=output_path,
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            fps=fps,
        )
        metadata = probe_media(output_path)
        asset.stored_filename = output_path.name
        asset.file_path = str(output_path)
        asset.file_size_bytes = output_path.stat().st_size
        asset.duration_seconds = metadata.get("duration_seconds") or duration_seconds
        asset.width = metadata.get("width") or width
        asset.height = metadata.get("height") or height
        asset.fps = metadata.get("fps") or fps
        asset.status = AIAssetStatus.READY.value
    except FFmpegError as exc:
        asset.status = AIAssetStatus.FAILED.value
        asset.error_message = str(exc)
    tag_values = tags.split(",") if tags else []
    set_ai_asset_tags(db, asset, tag_values)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/ai-assets/{asset_id}/file")
def get_ai_asset_file(
    asset_id: int, request: Request, db: Session = Depends(get_db)
) -> FileResponse:
    user = current_user_from_request(request, db)
    asset = db.get(AIAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="AI asset not found")
    ensure_ai_asset_visible(asset, user)
    path = Path(asset.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="AI asset file not found")
    return FileResponse(path, media_type=asset.mime_type, filename=asset.original_filename)


@router.patch("/ai-assets/{asset_id}", response_model=AIAssetRead)
def update_ai_asset(
    asset_id: int,
    payload: AIAssetUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> AIAssetRead:
    user = current_user_from_request(request, db)
    asset = db.get(AIAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="AI asset not found")
    ensure_ai_asset_visible(asset, user)
    if asset.scope == "system" and asset.user_id is None:
        raise HTTPException(status_code=403, detail="System AI assets are read-only")
    update_data = payload.model_dump(exclude_unset=True)
    for field in ("title", "asset_type", "prompt", "provider"):
        if field in update_data:
            setattr(asset, field, update_data[field])
    if "tags" in update_data:
        set_ai_asset_tags(db, asset, update_data["tags"])
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/ai-assets/{asset_id}/archive", response_model=AIAssetRead)
def archive_ai_asset(
    asset_id: int, request: Request, db: Session = Depends(get_db)
) -> AIAssetRead:
    user = current_user_from_request(request, db)
    asset = db.get(AIAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="AI asset not found")
    ensure_ai_asset_visible(asset, user)
    if asset.scope == "system" and asset.user_id is None:
        raise HTTPException(status_code=403, detail="System AI assets are read-only")
    asset.status = AIAssetStatus.ARCHIVED.value
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/ai-clone/workflows", response_model=List[AICloneWorkflowRead])
def list_ai_clone_workflows(db: Session = Depends(get_db)) -> List[AICloneWorkflowRead]:
    seed_ai_clone_workflows(db)
    return list(
        db.scalars(
            select(AICloneWorkflow)
            .where(AICloneWorkflow.status == "active")
            .order_by(AICloneWorkflow.name.asc())
        )
    )


@router.get("/ai-clone/provider-status")
def ai_clone_provider_status() -> Dict[str, Any]:
    configured = settings.ai_clone_provider == "mock" or bool(settings.comfyui_base_url)
    return {
        "provider": settings.ai_clone_provider,
        "configured": configured,
        "endpoint_configured": bool(settings.comfyui_base_url),
        "api_key_configured": bool(settings.comfyui_api_key),
        "image_workflow_configured": bool(settings.ai_clone_image_workflow_path),
        "video_workflow_configured": bool(settings.ai_clone_video_workflow_path),
        "poll_interval_seconds": settings.comfyui_poll_interval_seconds,
        "max_wait_seconds": settings.comfyui_max_wait_seconds,
    }


@router.get("/ai-clone/jobs", response_model=List[AICloneJobRead])
def list_ai_clone_jobs(
    request: Request,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(default=None),
) -> List[AICloneJobRead]:
    user = current_user_from_request(request, db)
    refresh_ai_clone_queue_positions(db, user.id)
    query = select(AICloneJob).where(AICloneJob.user_id == user.id)
    if status:
        query = query.where(AICloneJob.status == status)
    db.commit()
    return list(db.scalars(query.order_by(AICloneJob.created_at.desc(), AICloneJob.id.desc())))


@router.post("/ai-clone/jobs", response_model=AICloneJobRead)
async def create_ai_clone_job(
    request: Request,
    file: UploadFile = File(...),
    workflow_id: Optional[str] = Form(default=None),
    title: Optional[str] = Form(default=None),
    prompt: str = Form(...),
    negative_prompt: Optional[str] = Form(default=None),
    asset_type: str = Form(default=AIAssetType.BROLL.value),
    tags: Optional[str] = Form(default=None),
    duration_seconds: float = Form(default=4.0),
    similarity: float = Form(default=0.75),
    motion_strength: float = Form(default=0.45),
    reference_frame_strategy: str = Form(default="auto_representative"),
    simulated_queue_ahead: int = Form(default=0),
    db: Session = Depends(get_db),
) -> AICloneJobRead:
    user = current_user_from_request(request, db)
    reference_type = ai_clone_reference_type_for_upload(file)
    resolved_workflow_id = workflow_id or (
        "image_clone_video_v1" if reference_type == "image" else "video_clone_clip_v1"
    )
    workflow = ai_clone_workflow_for_id(db, resolved_workflow_id)
    if reference_type == "image" and workflow.mode != "image_to_video":
        raise HTTPException(status_code=400, detail="图片参考素材只能使用原图仿制 workflow")
    if reference_type == "video" and workflow.mode != "video_to_video":
        raise HTTPException(status_code=400, detail="视频参考素材只能使用原视频仿制 workflow")
    if asset_type not in {item.value for item in AIAssetType}:
        raise HTTPException(status_code=400, detail="请选择有效的视频片段用途")
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="请填写仿制目标 prompt")
    if duration_seconds < 2 or duration_seconds > 8:
        raise HTTPException(status_code=400, detail="仿制片段时长需要在 2-8 秒之间")
    if similarity < 0 or similarity > 1 or motion_strength < 0 or motion_strength > 1:
        raise HTTPException(status_code=400, detail="相似度和运动强度需要在 0-1 之间")
    if reference_frame_strategy not in {
        "auto_representative",
        "first_frame",
        "middle_frame",
        "uploaded_image",
    }:
        raise HTTPException(status_code=400, detail="请选择有效的参考帧方式")
    if reference_type == "video" and reference_frame_strategy == "uploaded_image":
        raise HTTPException(status_code=400, detail="视频参考素材不能使用“上传参考图”方式")
    if simulated_queue_ahead < 0 or simulated_queue_ahead > 20:
        raise HTTPException(status_code=400, detail="模拟排队人数需要在 0-20 之间")

    original_filename = file.filename or f"reference.{reference_type}"
    tag_values = normalize_ai_asset_tags(parse_tag_text(tags) + ["clone", workflow.mode])
    now = datetime.utcnow()
    job = AICloneJob(
        user_id=user.id,
        workflow_id=workflow.workflow_id,
        mode=workflow.mode,
        provider=workflow.provider,
        reference_asset_type=reference_type,
        reference_file_path="",
        reference_filename=original_filename,
        title=title or f"{Path(original_filename).stem} 仿制片段",
        prompt=prompt.strip(),
        negative_prompt=negative_prompt.strip() if negative_prompt else None,
        asset_type=asset_type,
        tags_json=tag_values,
        input_params_json={
            "duration_seconds": duration_seconds,
            "similarity": similarity,
            "motion_strength": motion_strength,
            "reference_frame_strategy": reference_frame_strategy,
        },
        status=AICloneJobStatus.QUEUED.value,
        estimated_credits=workflow.estimated_credits,
        estimated_seconds=workflow.estimated_seconds,
        queue_entered_at=now,
        progress_percent=0,
        progress_message=(
            f"前面还有 {simulated_queue_ahead} 个模拟任务"
            if simulated_queue_ahead
            else "已加入仿制生成队列"
        ),
        simulated_queue_ahead=simulated_queue_ahead,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    destination = ai_clone_reference_path(job.id, original_filename)
    await save_upload_file(file, destination)
    job.reference_file_path = str(destination)
    create_ai_clone_event(
        db,
        job,
        AICloneJobStatus.QUEUED.value,
        progress_percent=0,
        message=(
            f"已加入仿制生成队列，前面还有 {simulated_queue_ahead} 个模拟任务"
            if simulated_queue_ahead
            else "已加入仿制生成队列"
        ),
    )
    refresh_ai_clone_queue_positions(db, user.id)
    db.commit()
    db.refresh(job)
    enqueue_ai_clone_job(job.id, job.provider)
    return job


@router.get("/ai-clone/jobs/{job_id}", response_model=AICloneJobRead)
def get_ai_clone_job(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> AICloneJobRead:
    user = current_user_from_request(request, db)
    job = db.get(AICloneJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="仿制任务不存在")
    refresh_ai_clone_queue_positions(db, user.id)
    db.commit()
    db.refresh(job)
    return job


@router.get("/ai-clone/jobs/{job_id}/events", response_model=List[AICloneJobEventRead])
def list_ai_clone_job_events(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> List[AICloneJobEventRead]:
    user = current_user_from_request(request, db)
    job = db.get(AICloneJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="仿制任务不存在")
    return list(
        db.scalars(
            select(AICloneJobEvent)
            .where(AICloneJobEvent.job_id == job.id)
            .order_by(AICloneJobEvent.created_at.asc(), AICloneJobEvent.id.asc())
        )
    )


@router.post("/ai-clone/jobs/{job_id}/cancel", response_model=AICloneJobRead)
def cancel_ai_clone_job(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> AICloneJobRead:
    user = current_user_from_request(request, db)
    job = db.get(AICloneJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="仿制任务不存在")
    if job.status in {AICloneJobStatus.SUCCEEDED.value, AICloneJobStatus.FAILED.value}:
        raise HTTPException(status_code=400, detail="任务已结束，不能取消")
    job.finished_at = datetime.utcnow()
    create_ai_clone_event(
        db,
        job,
        AICloneJobStatus.CANCELLED.value,
        progress_percent=job.progress_percent,
        message="任务已取消，未扣除 credits",
    )
    refresh_ai_clone_queue_positions(db, user.id)
    db.commit()
    db.refresh(job)
    return job


@router.post("/ai-clone/jobs/{job_id}/retry", response_model=AICloneJobRead)
def retry_ai_clone_job(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> AICloneJobRead:
    user = current_user_from_request(request, db)
    job = db.get(AICloneJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="仿制任务不存在")
    if job.status not in {
        AICloneJobStatus.FAILED.value,
        AICloneJobStatus.CANCELLED.value,
        AICloneJobStatus.REFUNDED.value,
    }:
        raise HTTPException(status_code=400, detail="只有失败或取消的任务可以重新发起")
    if job.retry_count >= job.max_retries:
        raise HTTPException(status_code=400, detail="已达到最大重试次数")
    job.retry_count += 1
    job.status = AICloneJobStatus.QUEUED.value
    job.queue_entered_at = datetime.utcnow()
    job.started_at = None
    job.provider_started_at = None
    job.postprocess_started_at = None
    job.finished_at = None
    job.output_asset_id = None
    job.error_message = None
    create_ai_clone_event(
        db,
        job,
        AICloneJobStatus.QUEUED.value,
        progress_percent=0,
        message="已重新加入仿制生成队列",
    )
    refresh_ai_clone_queue_positions(db, user.id)
    db.commit()
    db.refresh(job)
    enqueue_ai_clone_job(job.id, job.provider)
    return job


def create_ai_clone_worker(db: Session, job: AICloneJob, provider: str) -> AICloneWorker:
    worker = AICloneWorker(
        provider=provider,
        cloud_region="configured" if provider == "comfyui" else "local",
        gpu_type="rtx4090" if provider == "comfyui" else "mock-rtx4090",
        status=AICloneWorkerStatus.STARTING.value,
        endpoint_url_secret_ref=(
            "FLASHCUTTER_COMFYUI_BASE_URL" if provider == "comfyui" else None
        ),
        current_job_id=job.id,
        started_at=datetime.utcnow(),
        cost_per_second_estimate=None if provider == "comfyui" else 0.0,
    )
    db.add(worker)
    db.flush()
    return worker


def start_ai_clone_job(
    job_id: int,
    provider: str,
    message: str,
    simulated_queue: bool = False,
) -> bool:
    with SessionLocal() as db:
        job = db.get(AICloneJob, job_id)
        if job is None:
            return False
        if job.status != AICloneJobStatus.QUEUED.value:
            return False
        job.simulated_queue_ahead = 0 if simulated_queue else job.simulated_queue_ahead
        job.queue_position = 1
        worker = create_ai_clone_worker(db, job, provider)
        job.worker_id = worker.id
        job.started_at = datetime.utcnow()
        job.wait_seconds = (job.started_at - job.queue_entered_at).total_seconds()
        create_ai_clone_event(
            db,
            job,
            AICloneJobStatus.STARTING_WORKER.value,
            progress_percent=8,
            message=message,
        )
        refresh_ai_clone_queue_positions(db, job.user_id)
        db.commit()
        return True


def reference_frame_timestamp(source_path: Path, strategy: str) -> float:
    if strategy == "first_frame":
        return 0.0
    metadata = probe_media(source_path)
    duration = float(metadata.get("duration_seconds") or 0.0)
    if duration <= 0:
        return 0.0
    if strategy == "middle_frame":
        return max(0.0, min(duration - 0.1, duration * 0.5))
    return max(0.0, min(duration - 0.1, duration * 0.4))


def ltx_frame_count(duration_seconds: float, frame_rate: int = 12) -> int:
    raw_frames = max(9, int(round(duration_seconds * frame_rate)))
    return max(9, 9 + int(round((raw_frames - 9) / 8)) * 8)


def ltx_reference_strength(similarity: float) -> float:
    return round(max(0.4, min(0.95, 0.35 + similarity * 0.6)), 2)


def ltx_sampling_steps(motion_strength: float) -> int:
    return max(6, min(14, int(round(6 + motion_strength * 8))))


def ltx_cfg(motion_strength: float) -> float:
    return round(max(2.2, min(3.8, 2.2 + motion_strength * 1.6)), 1)


def ltx_dimensions_for_reference(reference_path: Path) -> Dict[str, int]:
    try:
        metadata = probe_media(reference_path)
        width = int(metadata.get("width") or 512)
        height = int(metadata.get("height") or 320)
    except Exception:
        width, height = 512, 320
    if width <= 0 or height <= 0:
        width, height = 512, 320
    max_pixels = 512 * 512
    scale = min(1.0, (max_pixels / float(width * height)) ** 0.5)
    scaled_width = max(320, int(round(width * scale / 32)) * 32)
    scaled_height = max(320, int(round(height * scale / 32)) * 32)
    return {"width": scaled_width, "height": scaled_height}


def ai_clone_workflow_values(
    *,
    prompt: str,
    negative_prompt: str,
    uploaded_reference: str,
    duration_seconds: float,
    similarity: float,
    motion_strength: float,
    conditioning_path: Path,
) -> Dict[str, Any]:
    frame_rate = 12
    dimensions = ltx_dimensions_for_reference(conditioning_path)
    return {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "reference_file": uploaded_reference,
        "duration_seconds": duration_seconds,
        "duration_frames": ltx_frame_count(duration_seconds, frame_rate),
        "frame_rate": frame_rate,
        "reference_strength": ltx_reference_strength(similarity),
        "sampling_steps": ltx_sampling_steps(motion_strength),
        "cfg": ltx_cfg(motion_strength),
        "width": dimensions["width"],
        "height": dimensions["height"],
    }


def run_mock_ai_clone_job(job_id: int) -> None:
    with SessionLocal() as db:
        job = db.get(AICloneJob, job_id)
        if job is None:
            return
        if job.status != AICloneJobStatus.QUEUED.value:
            return
        simulated_queue_ahead = max(0, int(job.simulated_queue_ahead or 0))

    while simulated_queue_ahead > 0:
        with SessionLocal() as db:
            job = db.get(AICloneJob, job_id)
            if job is None:
                return
            if job.status != AICloneJobStatus.QUEUED.value:
                return
            job.simulated_queue_ahead = simulated_queue_ahead
            job.queue_position = simulated_queue_ahead + 1
            create_ai_clone_event(
                db,
                job,
                AICloneJobStatus.QUEUED.value,
                progress_percent=0,
                message=f"排队中：前面还有 {simulated_queue_ahead} 个任务",
            )
            db.commit()
        time.sleep(3)
        simulated_queue_ahead -= 1

    if not start_ai_clone_job(
        job_id,
        "mock",
        "正在启动 mock GPU worker",
        simulated_queue=True,
    ):
        return

    try:
        mock_ai_clone_checkpoint(job_id, AICloneJobStatus.WARMING_MODELS.value, 18, "正在加载仿制 workflow", 2.0)
        mock_ai_clone_checkpoint(job_id, AICloneJobStatus.SUBMITTING.value, 28, "正在提交 ComfyUI workflow", 1.0)
        mock_ai_clone_checkpoint(job_id, AICloneJobStatus.WAITING_PROVIDER.value, 38, "等待生成服务开始执行", 1.0)
        mock_ai_clone_checkpoint(job_id, AICloneJobStatus.RUNNING.value, 58, "生成中，正在模拟云端仿制", 4.0)
        mock_ai_clone_checkpoint(job_id, AICloneJobStatus.POSTPROCESSING.value, 78, "正在下载、转码和生成封面", 1.0)
        finish_mock_ai_clone_job(job_id)
    except Exception as exc:
        fail_mock_ai_clone_job(job_id, exc)


def run_comfyui_ai_clone_job(job_id: int) -> None:
    if not settings.comfyui_base_url:
        fail_mock_ai_clone_job(job_id, RuntimeError("未配置 ComfyUI endpoint"))
        return
    if not start_ai_clone_job(job_id, "comfyui", "正在连接 ComfyUI worker"):
        return

    try:
        with SessionLocal() as db:
            job = db.get(AICloneJob, job_id)
            if job is None:
                return
            workflow = db.scalar(
                select(AICloneWorkflow).where(
                    AICloneWorkflow.workflow_id == job.workflow_id
                )
            )
            if workflow is None:
                raise RuntimeError("仿制 workflow 不存在")
            if not workflow.workflow_api_json:
                raise RuntimeError("ComfyUI workflow JSON 未配置")
            workflow_api_json = workflow.workflow_api_json
            manifest_json = workflow.manifest_json or {}
            reference_path = Path(job.reference_file_path)
            conditioning_path = reference_path
            if job.reference_asset_type == "video":
                conditioning_path = ai_clone_conditioning_image_path(job.id)
                frame_strategy = str(
                    job.input_params_json.get("reference_frame_strategy")
                    or "auto_representative"
                )
                extract_video_frame(
                    reference_path,
                    conditioning_path,
                    timestamp_seconds=reference_frame_timestamp(
                        reference_path, frame_strategy
                    ),
                )
            prompt = job.prompt
            negative_prompt = job.negative_prompt or ""
            duration_seconds = float(job.input_params_json.get("duration_seconds") or 4.0)
            similarity = float(job.input_params_json.get("similarity") or 0.75)
            motion_strength = float(job.input_params_json.get("motion_strength") or 0.45)

        client = ComfyUIClient(
            base_url=settings.comfyui_base_url,
            api_key=settings.comfyui_api_key,
            timeout_seconds=settings.comfyui_timeout_seconds,
            poll_interval_seconds=settings.comfyui_poll_interval_seconds,
            max_wait_seconds=settings.comfyui_max_wait_seconds,
        )
        mock_ai_clone_checkpoint(
            job_id,
            AICloneJobStatus.WARMING_MODELS.value,
            18,
            "正在检查 ComfyUI worker 状态",
            0.0,
        )
        client.healthcheck()
        uploaded_reference = client.upload_input(conditioning_path)
        bound_workflow = workflow_with_bindings(
            workflow_api_json,
            manifest_json.get("bindings") or default_comfyui_workflow_bindings(),
            ai_clone_workflow_values(
                prompt=prompt,
                negative_prompt=negative_prompt,
                uploaded_reference=uploaded_reference,
                duration_seconds=duration_seconds,
                similarity=similarity,
                motion_strength=motion_strength,
                conditioning_path=conditioning_path,
            ),
        )
        mock_ai_clone_checkpoint(
            job_id,
            AICloneJobStatus.SUBMITTING.value,
            28,
            "正在提交 ComfyUI workflow",
            0.0,
        )
        provider_job_id = client.submit_prompt(bound_workflow)
        with SessionLocal() as db:
            job = db.get(AICloneJob, job_id)
            if job is None:
                return
            job.provider_job_id = provider_job_id
            db.commit()
        mock_ai_clone_checkpoint(
            job_id,
            AICloneJobStatus.WAITING_PROVIDER.value,
            38,
            "ComfyUI 已接收任务，等待生成结果",
            0.0,
        )
        mock_ai_clone_checkpoint(
            job_id,
            AICloneJobStatus.RUNNING.value,
            58,
            "ComfyUI 正在生成仿制片段",
            0.0,
        )
        output = client.wait_for_output(provider_job_id)
        mock_ai_clone_checkpoint(
            job_id,
            AICloneJobStatus.POSTPROCESSING.value,
            78,
            "正在下载、转码和生成封面",
            0.0,
        )
        output_path = ai_clone_output_path(job_id)
        client.download_output(output, output_path)
        import_ai_clone_output_asset(
            job_id,
            output_path,
            provider="comfyui_ai_clone",
            raw_response={"prompt_id": provider_job_id, "output": output},
        )
    except Exception as exc:
        fail_mock_ai_clone_job(job_id, exc)


def mock_ai_clone_checkpoint(
    job_id: int,
    status: str,
    progress_percent: int,
    message: str,
    sleep_seconds: float,
) -> None:
    time.sleep(sleep_seconds)
    with SessionLocal() as db:
        job = db.get(AICloneJob, job_id)
        if job is None:
            return
        if job.status == AICloneJobStatus.CANCELLED.value:
            raise RuntimeError("任务已取消")
        if status == AICloneJobStatus.RUNNING.value:
            job.provider_started_at = job.provider_started_at or datetime.utcnow()
        if status == AICloneJobStatus.POSTPROCESSING.value:
            job.postprocess_started_at = job.postprocess_started_at or datetime.utcnow()
        if job.worker_id:
            worker = db.get(AICloneWorker, job.worker_id)
            if worker is not None:
                worker.status = (
                    AICloneWorkerStatus.WARMING_MODELS.value
                    if status == AICloneJobStatus.WARMING_MODELS.value
                    else AICloneWorkerStatus.RUNNING.value
                )
                worker.last_heartbeat_at = datetime.utcnow()
                if status == AICloneJobStatus.WARMING_MODELS.value:
                    worker.ready_at = datetime.utcnow()
        create_ai_clone_event(
            db,
            job,
            status,
            progress_percent=progress_percent,
            message=message,
            raw_response_json={"mock": True},
        )
        db.commit()


def import_ai_clone_output_asset(
    job_id: int,
    output_path: Path,
    provider: str,
    raw_response: Optional[Dict[str, Any]] = None,
) -> None:
    with SessionLocal() as db:
        job = db.get(AICloneJob, job_id)
        if job is None:
            return
        if job.status == AICloneJobStatus.CANCELLED.value:
            return
        if not output_path.exists():
            raise FFmpegError("生成结果文件不存在，无法入库")

        create_ai_clone_event(
            db,
            job,
            AICloneJobStatus.IMPORTING.value,
            progress_percent=88,
            message="正在写入视频片段库",
            raw_response_json=raw_response or {"output_path": str(output_path)},
        )
        asset = AIAsset(
            user_id=job.user_id,
            scope="private",
            provider=provider,
            asset_kind=AIAssetKind.VIDEO.value,
            asset_type=job.asset_type,
            title=job.title,
            prompt=job.prompt,
            source_image_path=job.reference_file_path,
            original_filename=f"clone-job-{job.id}.mp4",
            stored_filename="",
            file_path="",
            mime_type="video/mp4",
            generation_cost=float(job.estimated_credits),
            status=AIAssetStatus.IMPORTING.value,
        )
        db.add(asset)
        db.flush()
        asset_output_path = ai_asset_generated_video_path(asset.id)
        shutil.copyfile(output_path, asset_output_path)
        metadata = probe_media(asset_output_path)
        asset.stored_filename = asset_output_path.name
        asset.file_path = str(asset_output_path)
        asset.file_size_bytes = asset_output_path.stat().st_size
        asset.duration_seconds = metadata.get("duration_seconds")
        asset.width = metadata.get("width")
        asset.height = metadata.get("height")
        asset.fps = metadata.get("fps")
        asset.generation_time_seconds = (
            datetime.utcnow() - (job.started_at or job.created_at)
        ).total_seconds()
        asset.status = AIAssetStatus.READY.value
        set_ai_asset_tags(db, asset, job.tags_json)

        finished_at = datetime.utcnow()
        job.output_asset_id = asset.id
        job.actual_credits = job.estimated_credits
        job.finished_at = finished_at
        job.elapsed_seconds = (finished_at - (job.started_at or job.created_at)).total_seconds()
        create_ai_clone_event(
            db,
            job,
            AICloneJobStatus.SUCCEEDED.value,
            progress_percent=100,
            message="仿制片段已加入视频片段库",
            raw_response_json={"asset_id": asset.id, **(raw_response or {})},
        )
        if job.worker_id:
            worker = db.get(AICloneWorker, job.worker_id)
            if worker is not None:
                worker.status = AICloneWorkerStatus.STOPPED.value
                worker.current_job_id = None
                worker.idle_since = finished_at
                worker.last_heartbeat_at = finished_at
        db.commit()


def finish_mock_ai_clone_job(job_id: int) -> None:
    with SessionLocal() as db:
        job = db.get(AICloneJob, job_id)
        if job is None:
            return
        if job.status == AICloneJobStatus.CANCELLED.value:
            return
        reference_path = Path(job.reference_file_path)
        if not reference_path.exists():
            raise FFmpegError("参考素材文件不存在，无法生成")
        output_path = ai_clone_output_path(job.id)
        duration_seconds = float(job.input_params_json.get("duration_seconds") or 4.0)
        if job.reference_asset_type == "image":
            render_image_motion_clip(
                image_path=reference_path,
                output_path=output_path,
                duration_seconds=duration_seconds,
                width=1080,
                height=1920,
                fps=30.0,
            )
        else:
            render_timeline(
                [reference_path],
                concat_list_path(100000 + job.id),
                output_path,
                width=1080,
                height=1920,
                fps=30.0,
                fit="cover",
                transformations={
                    "visual_style": "clean_ad",
                    "finishing_style": "sharpen",
                    "brightness": 0.02,
                    "contrast": 1.06,
                    "saturation": 1.08,
                },
            )
    import_ai_clone_output_asset(
        job_id,
        output_path,
        provider="mock_ai_clone",
        raw_response={"mock_output_path": str(output_path)},
    )


def fail_mock_ai_clone_job(job_id: int, exc: Exception) -> None:
    operator_message = ai_clone_operator_error(exc)
    with SessionLocal() as db:
        job = db.get(AICloneJob, job_id)
        if job is None:
            return
        if job.status == AICloneJobStatus.CANCELLED.value:
            return
        job.actual_credits = 0
        job.finished_at = datetime.utcnow()
        job.elapsed_seconds = (
            job.finished_at - (job.started_at or job.created_at)
        ).total_seconds()
        create_ai_clone_event(
            db,
            job,
            AICloneJobStatus.FAILED.value,
            progress_percent=job.progress_percent,
            message=operator_message,
            error_message=operator_message,
            raw_response_json={"error": str(exc)},
        )
        if job.worker_id:
            worker = db.get(AICloneWorker, job.worker_id)
            if worker is not None:
                worker.status = AICloneWorkerStatus.FAILED.value
                worker.current_job_id = None
                worker.last_heartbeat_at = datetime.utcnow()
        db.commit()


def ai_clone_operator_error(exc: Exception) -> str:
    detail = str(exc)
    lowered = detail.lower()
    if "cannot connect" in lowered or "connection refused" in lowered:
        return "生成服务暂时连接不上，任务未扣费。请确认 ComfyUI 已启动后重试。"
    if "timed out" in lowered or "timeout" in lowered:
        return "生成服务响应超时，任务未扣费。可降低时长、换一段参考视频或稍后重试。"
    if "workflow json" in lowered or "workflow" in lowered and "未配置" in detail:
        return "仿制 workflow 尚未配置完成，任务未扣费。请先完成生成服务配置。"
    if "node_errors" in lowered or "prompt outputs failed validation" in lowered:
        return "生成参数与当前 workflow 不匹配，任务未扣费。请降低时长或联系管理员检查 workflow。"
    if "no output" in lowered or "没有产出" in detail:
        return "生成服务已启动，但没有产出视频。可降低时长、换参考视频或修改 prompt 后重试。"
    if "参考素材文件不存在" in detail:
        return "参考素材文件缺失，任务未扣费。请重新上传参考视频或图片。"
    return "生成失败，任务未扣费。可降低时长、换参考视频或修改 prompt 后重试。"


@router.post("/assets/upload", response_model=AssetRead)
async def upload_asset(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> AssetRead:
    asset = create_pending_asset(
        db=db,
        original_filename=file.filename or "upload.mp4",
        mime_type=file.content_type,
    )
    destination = asset_upload_path(asset.id, asset.original_filename)
    file_size = await save_upload_file(file, destination)
    return finalize_asset_file(db=db, asset=asset, destination=destination, file_size=file_size)


@router.post("/assets/import-url", response_model=AssetRead)
def import_asset_url(payload: AssetImportUrl, db: Session = Depends(get_db)) -> AssetRead:
    original_filename = payload.filename or filename_from_url(payload.url)

    def save_remote_file(destination: Path) -> int:
        request = UrlRequest(payload.url, headers={"User-Agent": "flashcutter-mvp/0.1"})
        try:
            with urlopen(request, timeout=60) as response:
                destination.parent.mkdir(parents=True, exist_ok=True)
                size = 0
                with destination.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        output.write(chunk)
                return size
        except URLError as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download URL: {exc}") from exc

    asset = create_pending_asset(
        db=db,
        original_filename=original_filename,
        mime_type="video/mp4",
    )
    destination = asset_upload_path(asset.id, asset.original_filename)
    file_size = save_remote_file(destination)
    return finalize_asset_file(db=db, asset=asset, destination=destination, file_size=file_size)


def create_pending_asset(
    db: Session, original_filename: str, mime_type: Optional[str]
) -> Asset:
    asset = Asset(
        original_filename=original_filename,
        stored_filename="pending",
        file_path="pending",
        mime_type=mime_type,
        status=AssetStatus.UPLOADED.value,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def finalize_asset_file(
    db: Session, asset: Asset, destination: Path, file_size: int
) -> Asset:
    asset.stored_filename = destination.name
    asset.file_path = str(destination)
    asset.file_size_bytes = file_size

    try:
        metadata = probe_media(destination)
        asset.duration_seconds = metadata["duration_seconds"]
        asset.width = metadata["width"]
        asset.height = metadata["height"]
        asset.fps = metadata["fps"]
        asset.status = AssetStatus.READY.value
    except FFmpegError as exc:
        asset.status = AssetStatus.FAILED.value
        asset.error_message = str(exc)

    db.commit()
    db.refresh(asset)
    return asset


@router.get("/assets", response_model=List[AssetRead])
def list_assets(db: Session = Depends(get_db)) -> List[AssetRead]:
    return list(db.scalars(select(Asset).order_by(Asset.created_at.desc())))


@router.post("/assets/{asset_id}/segment", response_model=List[SegmentRead])
def segment_asset(
    asset_id: int,
    segment_seconds: float = 3.0,
    db: Session = Depends(get_db),
) -> List[SegmentRead]:
    return segment_asset_for_task(db=db, asset_id=asset_id, segment_seconds=segment_seconds)


def segment_asset_for_task(
    db: Session, asset_id: int, segment_seconds: float = 3.0
) -> List[Segment]:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not asset.duration_seconds:
        raise HTTPException(status_code=400, detail="Asset must be probed before splitting")

    for existing in list(asset.segments):
        db.delete(existing)
    db.flush()

    try:
        generated_segments = split_fixed_segments(
            source_path=Path(asset.file_path),
            output_dir=asset_segments_dir(asset.id),
            duration_seconds=asset.duration_seconds,
            segment_seconds=segment_seconds,
        )
    except FFmpegError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    segments = []
    for item in generated_segments:
        segment = Segment(
            asset_id=asset.id,
            segment_index=item["index"],
            start_time=item["start_time"],
            end_time=item["end_time"],
            duration_seconds=item["duration_seconds"],
            file_path=item["file_path"],
            detection_method="fixed_interval",
            status=SegmentStatus.READY.value,
        )
        db.add(segment)
        segments.append(segment)
    db.commit()
    for segment in segments:
        db.refresh(segment)
    return segments


@router.get("/assets/{asset_id}/segments", response_model=List[SegmentRead])
def list_segments(asset_id: int, db: Session = Depends(get_db)) -> List[SegmentRead]:
    return list(
        db.scalars(
            select(Segment)
            .where(Segment.asset_id == asset_id)
            .order_by(Segment.segment_index)
        )
    )


@router.get("/assets/{asset_id}/file")
def get_asset_file(asset_id: int, db: Session = Depends(get_db)) -> FileResponse:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    path = Path(asset.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Asset file not found")
    return FileResponse(path, media_type=asset.mime_type or "video/mp4", filename=asset.original_filename)


@router.post("/assets/{asset_id}/text-regions/detect", response_model=TextRegionDetectionRead)
def detect_asset_text_regions(
    asset_id: int, db: Session = Depends(get_db)
) -> TextRegionDetectionRead:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.status != AssetStatus.READY.value:
        raise HTTPException(status_code=400, detail="Asset must be ready before text detection")

    try:
        regions = detect_text_regions(
            source_path=Path(asset.file_path),
            output_dir=asset_analysis_dir(asset.id),
            width=asset.width,
            height=asset.height,
            duration_seconds=asset.duration_seconds,
        )
    except FFmpegError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return TextRegionDetectionRead(
        asset_id=asset.id,
        regions=regions,
        cover_regions=[
            {
                "x": region["x"],
                "y": region["y"],
                "width": region["width"],
                "height": region["height"],
                "color": "black@0.84",
            }
            for region in regions
        ],
    )


@router.get("/music", response_model=List[MusicTrackRead])
def list_music_tracks(
    request: Request, db: Session = Depends(get_db)
) -> List[MusicTrackRead]:
    user = optional_user_from_request(request, db)
    query = select(MusicTrack).where(MusicTrack.is_active.is_(True))
    if user is None:
        query = query.where(MusicTrack.scope == "system")
    else:
        query = query.where((MusicTrack.scope == "system") | (MusicTrack.user_id == user.id))
    return list(db.scalars(query.order_by(MusicTrack.scope.asc(), MusicTrack.created_at.desc())))


@router.post("/music/upload", response_model=MusicTrackRead)
async def upload_music_track(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
) -> MusicTrackRead:
    user = optional_user_from_request(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if file.content_type and not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Music upload must be an audio file")

    track = MusicTrack(
        user_id=user.id,
        title=title or Path(file.filename or "music").stem,
        original_filename=file.filename or "music.mp3",
        stored_filename="",
        file_path="",
        mime_type=file.content_type,
        scope="private",
        is_active=True,
    )
    db.add(track)
    db.commit()
    db.refresh(track)

    destination = music_upload_path(track.id, track.original_filename)
    size = await save_upload_file(file, destination)
    track.stored_filename = destination.name
    track.file_path = str(destination)
    track.file_size_bytes = size
    try:
        metadata = probe_media(destination)
        track.duration_seconds = metadata.get("duration_seconds")
    except FFmpegError:
        track.duration_seconds = None
    db.commit()
    db.refresh(track)
    return track


@router.get("/music/{track_id}/file")
def get_music_file(
    track_id: int, request: Request, db: Session = Depends(get_db)
) -> FileResponse:
    track = db.get(MusicTrack, track_id)
    if track is None or not track.is_active:
        raise HTTPException(status_code=404, detail="Music track not found")
    user = optional_user_from_request(request, db)
    if track.scope != "system" and (user is None or track.user_id != user.id):
        raise HTTPException(status_code=403, detail="Music track is private")
    path = Path(track.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Music file not found")
    return FileResponse(
        path,
        media_type=track.mime_type or "audio/mpeg",
        filename=track.original_filename,
    )


@router.get("/creative-references", response_model=List[CreativeReferenceRead])
def list_creative_references(
    component_type: Optional[str] = Query(default=None),
    industry: Optional[str] = Query(default=None),
    rights_status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> List[CreativeReferenceRead]:
    query = select(CreativeReference).where(CreativeReference.is_active.is_(True))
    if component_type:
        query = query.where(CreativeReference.component_type == component_type)
    if industry:
        query = query.where(CreativeReference.industry == industry)
    if rights_status:
        query = query.where(CreativeReference.rights_status == rights_status)
    return list(db.scalars(query.order_by(CreativeReference.updated_at.desc())))


@router.post("/creative-references", response_model=CreativeReferenceRead)
def create_creative_reference(
    payload: CreativeReferenceCreate, db: Session = Depends(get_db)
) -> CreativeReferenceRead:
    existing = db.scalar(
        select(CreativeReference).where(CreativeReference.source_url == payload.source_url)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Creative reference URL already exists")
    reference = CreativeReference(**payload.model_dump())
    db.add(reference)
    db.commit()
    db.refresh(reference)
    return reference


@router.post("/creative-references/import-url", response_model=CreativeReferenceRead)
def import_creative_reference_url(
    payload: CreativeReferenceImportRequest, db: Session = Depends(get_db)
) -> CreativeReferenceRead:
    existing = db.scalar(
        select(CreativeReference).where(CreativeReference.source_url == payload.url)
    )
    metadata = importable_metadata_for_url(payload.url)
    if payload.component_type:
        metadata["component_type"] = payload.component_type
    if payload.industry:
        metadata["industry"] = payload.industry
    if payload.style_tags:
        metadata["style_tags"] = payload.style_tags
    if payload.notes:
        existing_notes = metadata.get("notes")
        metadata["notes"] = f"{payload.notes}\n{existing_notes}" if existing_notes else payload.notes

    if existing is None:
        reference = CreativeReference(**metadata)
        db.add(reference)
    else:
        reference = existing
        for key, value in metadata.items():
            setattr(reference, key, value)
    db.commit()
    db.refresh(reference)
    return reference


@router.get("/templates", response_model=List[TemplateRead])
def list_templates(db: Session = Depends(get_db)) -> List[TemplateRead]:
    return list(db.scalars(select(Template).order_by(Template.name)))


@router.post("/templates", response_model=TemplateRead)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)) -> TemplateRead:
    existing = db.scalar(select(Template).where(Template.name == payload.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Template name already exists")

    template = Template(
        name=payload.name,
        description=payload.description,
        version=payload.version,
        json_spec=payload.json_spec,
        is_builtin=payload.is_builtin,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.post("/templates/validate", response_model=TemplateValidationRead)
def validate_template(payload: TemplateValidationRequest) -> TemplateValidationRead:
    normalized = compile_template_json_spec(payload.json_spec)
    return TemplateValidationRead(
        valid=True,
        normalized_spec=normalized.model_dump(exclude_none=True),
        warnings=template_warnings(normalized),
    )


@router.get("/templates/{template_id}", response_model=TemplateRead)
def get_template(template_id: int, db: Session = Depends(get_db)) -> TemplateRead:
    template = db.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/templates/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: int, payload: TemplateUpdate, db: Session = Depends(get_db)
) -> TemplateRead:
    template = db.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.is_builtin:
        raise HTTPException(
            status_code=400,
            detail="Built-in templates cannot be edited directly. Duplicate the template first.",
        )

    if payload.name is not None and payload.name != template.name:
        existing = db.scalar(select(Template).where(Template.name == payload.name))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Template name already exists")
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    if payload.version is not None:
        template.version = payload.version
    if payload.json_spec is not None:
        template.json_spec = payload.json_spec
    if payload.is_builtin is not None:
        template.is_builtin = payload.is_builtin

    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)) -> None:
    template = db.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.is_builtin:
        raise HTTPException(status_code=400, detail="Built-in templates cannot be deleted")
    db.delete(template)
    db.commit()


@router.post("/tasks", response_model=GenerationTaskRead)
def create_task(
    payload: GenerationTaskCreate, request: Request, db: Session = Depends(get_db)
) -> GenerationTaskRead:
    asset = db.get(Asset, payload.asset_id)
    template = db.get(Template, payload.template_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    user = optional_user_from_request(request, db)
    task = GenerationTask(
        name=payload.name,
        user_id=user.id if user else None,
        asset_id=asset.id,
        template_id=template.id,
        params_json=payload.params_json or {},
        status=TaskStatus.QUEUED.value,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    record_task_event(
        db=db,
        task=task,
        status=task.status,
        progress_percent=task.progress_percent,
        message="Task created",
    )
    return task


@router.post("/tasks/batch", response_model=List[GenerationTaskRead])
def create_tasks_for_templates(
    payload: GenerationTaskBatchCreate, request: Request, db: Session = Depends(get_db)
) -> List[GenerationTaskRead]:
    user = optional_user_from_request(request, db)
    return create_tasks_for_asset_templates(
        db=db,
        asset_id=payload.asset_id,
        template_ids=payload.template_ids,
        name_prefix=payload.name_prefix,
        production_run_id=payload.production_run_id,
        user_id=user.id if user else None,
        params_json=payload.params_json,
    )


def create_tasks_for_asset_templates(
    db: Session,
    asset_id: int,
    template_ids: List[int],
    name_prefix: str,
    production_run_id: Optional[int],
    user_id: Optional[int],
    params_json: Optional[dict],
) -> List[GenerationTask]:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    templates = list(
        db.scalars(select(Template).where(Template.id.in_(template_ids)))
    )
    found_ids = {template.id for template in templates}
    missing_ids = [template_id for template_id in template_ids if template_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Templates not found: {missing_ids}",
        )

    production_run = None
    revision_number = 1
    if production_run_id is not None:
        production_run = db.get(ProductionRun, production_run_id)
        if production_run is None:
            raise HTTPException(status_code=404, detail="Production run not found")
        if production_run.asset_id != asset.id:
            raise HTTPException(
                status_code=400,
                detail="Production run does not belong to this asset",
            )
        max_revision = max(
            (task.revision_number for task in production_run.generation_tasks),
            default=0,
        )
        revision_number = max_revision + 1
    else:
        production_run = ProductionRun(
            asset_id=asset.id,
            name=build_batch_task_prefix(asset=asset, name_prefix=name_prefix),
            name_prefix=" ".join(name_prefix.split()) or "variant-batch",
        )
        db.add(production_run)
        db.flush()

    tasks = []
    for template in templates:
        task = GenerationTask(
            name=f"{production_run.name} - {template.name}",
            user_id=user_id,
            production_run_id=production_run.id,
            revision_number=revision_number,
            asset_id=asset.id,
            template_id=template.id,
            params_json=params_json or {},
            status=TaskStatus.QUEUED.value,
        )
        db.add(task)
        tasks.append(task)
    db.commit()
    for task in tasks:
        db.refresh(task)
        record_task_event(
            db=db,
            task=task,
            status=task.status,
            progress_percent=task.progress_percent,
            message="Task created",
            commit=False,
        )
    db.commit()
    return tasks


def build_batch_task_prefix(asset: Asset, name_prefix: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    safe_asset_name = " ".join(asset.original_filename.split())
    safe_prefix = " ".join(name_prefix.split()) or "variant-batch"
    return f"{timestamp} {safe_asset_name} - {safe_prefix}"


@router.post("/assets/{asset_id}/render-variants", response_model=List[OutputReviewRead])
def render_asset_variants(
    asset_id: int,
    payload: RenderVariantsRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> List[OutputReviewRead]:
    user = optional_user_from_request(request, db)
    tasks = create_tasks_for_asset_templates(
        db=db,
        asset_id=asset_id,
        template_ids=payload.template_ids,
        name_prefix=payload.name_prefix,
        production_run_id=payload.production_run_id,
        user_id=user.id if user else None,
        params_json=payload.params_json,
    )
    outputs = []
    for task in tasks:
        task_result = run_task_pipeline(task.id, request=request, payload=None, db=db)
        outputs.append(output_review_payload_by_id(db, task_result.output.id))
    return outputs


@router.post("/assets/{asset_id}/render-variants/enqueue", response_model=List[GenerationTaskRead])
def enqueue_asset_variants(
    asset_id: int,
    payload: RenderVariantsRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> List[GenerationTaskRead]:
    user = optional_user_from_request(request, db)
    tasks = create_tasks_for_asset_templates(
        db=db,
        asset_id=asset_id,
        template_ids=payload.template_ids,
        name_prefix=payload.name_prefix,
        production_run_id=payload.production_run_id,
        user_id=user.id if user else None,
        params_json=payload.params_json,
    )
    for task in tasks:
        mark_task_progress(
            db=db,
            task=task,
            status=TaskStatus.WAITING.value,
            progress_percent=0,
            progress_message="Waiting in render queue",
            commit=False,
        )
    db.commit()
    for task in tasks:
        db.refresh(task)
        task_queue.enqueue(task.id, run_queued_task_pipeline)
    return tasks


@router.post("/assets/{asset_id}/render-variants/preflight", response_model=VariantPreflightRead)
def preflight_asset_variants(
    asset_id: int,
    payload: RenderVariantsRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> VariantPreflightRead:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    templates = list(db.scalars(select(Template).where(Template.id.in_(payload.template_ids))))
    found_ids = {template.id for template in templates}
    missing_ids = [template_id for template_id in payload.template_ids if template_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Templates not found: {missing_ids}")

    user = optional_user_from_request(request, db)
    ordered_templates = sorted(templates, key=lambda template: payload.template_ids.index(template.id))
    items = []
    for template in ordered_templates:
        task = GenerationTask(
            name="preflight",
            user_id=user.id if user else None,
            asset_id=asset.id,
            template_id=template.id,
            template=template,
            params_json=payload.params_json or {},
        )
        spec = template_spec_for_task(task)
        warnings = template_warnings(spec)
        missing_fields: List[str] = []
        ai_asset_slot_count = 0
        if (template.json_spec or {}).get("schema_version") == 3:
            template_v3 = TemplateSpecV3.model_validate(template.json_spec or {})
            missing_fields = v3_missing_runtime_fields(
                template_v3,
                (payload.params_json or {}).get("runtime_values", {}),
            )
            ai_asset_slots = media_slots_for_task(db=db, task=task, warnings=warnings)
            ai_asset_slot_count = len(
                [
                    operation
                    for operation in template_v3.operations
                    if operation.type in {"prepend_clip", "append_clip"} and operation.slot
                ]
            )
        else:
            recipe = TemplateSpec.model_validate(template.json_spec or {})
            ai_asset_slots = select_ai_asset_slots_for_recipe(
                db=db,
                task=task,
                recipe=recipe,
                warnings=warnings,
            )
            ai_asset_slot_count = len(ai_asset_slot_bindings(recipe))
        music_plan = None
        if spec.music.track_id is not None:
            try:
                music_plan = music_plan_for_task(db=db, task=task, template_spec=spec)
            except HTTPException as exc:
                warnings.append(str(exc.detail))
        transformations = spec.transformations.model_dump(exclude_none=True)
        segment_seconds = spec.segments.segment_seconds
        estimated_clip_count = estimate_clip_count(
            asset_duration=asset.duration_seconds,
            segment_seconds=segment_seconds,
            requested_count=spec.selection.count,
            max_duration=spec.selection.max_total_duration,
        )
        estimated_duration = (
            min(asset.duration_seconds or 0, estimated_clip_count * segment_seconds)
            if asset.duration_seconds
            else None
        )
        items.append(
            VariantPreflightItem(
                template_id=template.id,
                template_name=template.name,
                asset_id=asset.id,
                asset_filename=asset.original_filename,
                status="blocked" if missing_fields else ("warning" if warnings else "ready"),
                title=spec.creative_goal.title,
                estimated_clip_count=estimated_clip_count,
                estimated_duration_seconds=estimated_duration,
                output_width=spec.output.width,
                output_height=spec.output.height,
                output_fps=spec.output.fps,
                fit=spec.layout.fit,
                cover_region_count=len(transformations.get("cover_regions") or []),
                text_overlay_count=len(transformations.get("text_overlays") or []),
                ai_asset_slot_count=ai_asset_slot_count,
                selected_ai_asset_count=len(ai_asset_slots),
                ai_asset_slots=ai_asset_slots,
                playback_speed=transformations.get("playback_speed"),
                mute_audio=bool(transformations.get("mute_audio")),
                music_track_id=music_plan.get("track_id") if music_plan else None,
                music_title=music_plan.get("title") if music_plan else None,
                music_mode=music_plan.get("mode") if music_plan else None,
                music_volume=music_plan.get("volume") if music_plan else None,
                music_loop=bool(music_plan.get("loop")) if music_plan else False,
                warnings=warnings,
                missing_fields=missing_fields,
            )
        )

    return VariantPreflightRead(
        asset_id=asset.id,
        asset_filename=asset.original_filename,
        asset_duration_seconds=asset.duration_seconds,
        items=items,
    )


@router.post(
    "/expansion-plans/strong-opening/copy-suggestions",
    response_model=StrongOpeningCopyResponse,
)
def suggest_strong_opening_copy(
    payload: StrongOpeningCopyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> StrongOpeningCopyResponse:
    optional_user_from_request(request, db)
    asset = db.get(Asset, payload.asset_id) if payload.asset_id is not None else None
    if payload.asset_id is not None and asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    suggestions, warnings = opening_copy_suggestions(
        payload,
        settings=settings,
        asset_filename=asset.original_filename if asset else None,
    )
    return StrongOpeningCopyResponse(
        provider=settings.copy_ai_provider or "rule_based",
        model=settings.copy_ai_model or None,
        suggestions=suggestions,
        warnings=warnings,
    )


@router.post(
    "/expansion-runs/strong-opening/preflight",
    response_model=StrongOpeningExpansionPreflightRead,
)
def preflight_strong_opening_expansion(
    payload: StrongOpeningExpansionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> StrongOpeningExpansionPreflightRead:
    user = optional_user_from_request(request, db)
    return build_strong_opening_expansion_preflight(
        db=db,
        payload=payload,
        user_id=user.id if user else None,
    )


@router.post(
    "/expansion-runs/strong-opening/enqueue",
    response_model=List[GenerationTaskRead],
)
def enqueue_strong_opening_expansion(
    payload: StrongOpeningExpansionEnqueueRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> List[GenerationTaskRead]:
    user = optional_user_from_request(request, db)
    preflight = build_strong_opening_expansion_preflight(
        db=db,
        payload=payload,
        user_id=user.id if user else None,
    )
    if payload.preflight_token and payload.preflight_token != preflight.preflight_token:
        raise HTTPException(status_code=400, detail="Preflight token does not match current plan")
    if preflight.summary.blocked_count:
        raise HTTPException(
            status_code=400,
            detail="这批强开场任务还不能入队：请先处理预检中的阻塞项。",
        )

    asset = db.get(Asset, payload.asset_id)
    template = db.get(Template, preflight.template_id)
    if asset is None or template is None:
        raise HTTPException(status_code=404, detail="Asset or template not found")

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    safe_prefix = " ".join(payload.name_prefix.split()) or "strong-opening-expansion"
    run_name = f"{timestamp} {safe_prefix}"
    production_run = ProductionRun(
        asset_id=asset.id,
        name=run_name,
        name_prefix=safe_prefix,
    )
    db.add(production_run)
    db.flush()

    tasks: List[GenerationTask] = []
    for index, suggestion in enumerate(preflight.suggestions, start=1):
        task = GenerationTask(
            name=strong_opening_task_name(
                run_name=run_name,
                index=index,
                suggestion=suggestion,
            ),
            user_id=user.id if user else None,
            production_run_id=production_run.id,
            revision_number=1,
            asset_id=asset.id,
            template_id=template.id,
            params_json=strong_opening_task_params(
                payload=payload,
                suggestion=suggestion,
                variant_index=index,
                variant_count=len(preflight.suggestions),
                preflight=preflight,
            ),
            status=TaskStatus.QUEUED.value,
        )
        db.add(task)
        tasks.append(task)
    db.commit()

    for task in tasks:
        db.refresh(task)
        record_task_event(
            db=db,
            task=task,
            status=task.status,
            progress_percent=task.progress_percent,
            message="Task created from strong opening expansion",
            commit=False,
        )
        mark_task_progress(
            db=db,
            task=task,
            status=TaskStatus.WAITING.value,
            progress_percent=0,
            progress_message="Waiting in render queue",
            commit=False,
        )
    db.commit()
    for task in tasks:
        db.refresh(task)
        task_queue.enqueue(task.id, run_queued_task_pipeline)
    return tasks


def build_strong_opening_expansion_preflight(
    db: Session,
    payload: StrongOpeningExpansionRequest,
    user_id: Optional[int],
) -> StrongOpeningExpansionPreflightRead:
    if payload.asset_id is None:
        raise HTTPException(status_code=400, detail="请选择一条种子视频。")
    asset = db.get(Asset, payload.asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    template = strong_opening_template(db)
    suggestions, plan_warnings = strong_opening_suggestions_for_payload(
        payload=payload,
        asset=asset,
    )
    template_v3 = TemplateSpecV3.model_validate(template.json_spec or {})
    items: List[VariantPreflightItem] = []
    for index, suggestion in enumerate(suggestions, start=1):
        params_json = strong_opening_task_params(
            payload=payload,
            suggestion=suggestion,
            variant_index=index,
            variant_count=len(suggestions),
            preflight=None,
        )
        spec = compile_template_json_spec(template.json_spec or {}, params_json)
        warnings = template_warnings(spec)
        missing_fields = v3_missing_runtime_fields(
            template_v3,
            (params_json.get("runtime_values") or {}),
        )
        operation_labels = v3_operation_labels(template_v3)
        if template_v3.input_requirements.min_seed_duration_seconds and (
            asset.duration_seconds or 0
        ) < template_v3.input_requirements.min_seed_duration_seconds:
            warnings.append("视频时长低于强开场方案建议的最小时长。")
        if operation_labels:
            warnings.extend([f"将执行：{', '.join(operation_labels)}"])
        transformations = spec.transformations.model_dump(exclude_none=True)
        estimated_clip_count = estimate_clip_count(
            asset_duration=asset.duration_seconds,
            segment_seconds=spec.segments.segment_seconds,
            requested_count=spec.selection.count,
            max_duration=spec.selection.max_total_duration,
        )
        estimated_duration = (
            min(asset.duration_seconds or 0, estimated_clip_count * spec.segments.segment_seconds)
            if asset.duration_seconds
            else None
        )
        items.append(
            VariantPreflightItem(
                asset_id=asset.id,
                asset_filename=asset.original_filename,
                template_id=template.id,
                template_name=template.name,
                status="blocked" if missing_fields else ("warning" if warnings else "ready"),
                title=f"强开场 #{index}: {suggestion.text}",
                estimated_clip_count=estimated_clip_count,
                estimated_duration_seconds=estimated_duration,
                output_width=spec.output.width,
                output_height=spec.output.height,
                output_fps=spec.output.fps,
                fit=spec.layout.fit,
                cover_region_count=len(transformations.get("cover_regions") or []),
                text_overlay_count=len(transformations.get("text_overlays") or []),
                playback_speed=transformations.get("playback_speed"),
                mute_audio=bool(transformations.get("mute_audio")),
                warnings=warnings,
                missing_fields=missing_fields,
            )
        )

    ready_count = len([item for item in items if item.status == "ready"])
    warning_count = len([item for item in items if item.status == "warning"])
    blocked_count = len([item for item in items if item.status == "blocked"])
    token_payload = {
        "asset_id": payload.asset_id,
        "opening_texts": [suggestion.text for suggestion in suggestions],
        "intensity": payload.intensity,
        "output_preset_id": payload.output_preset_id,
        "name_prefix": payload.name_prefix,
        "template_id": template.id,
    }
    return StrongOpeningExpansionPreflightRead(
        preflight_token=hashlib.sha256(
            json.dumps(token_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        summary=ProductionRunPreflightSummary(
            asset_count=1,
            template_count=1,
            task_count=len(items),
            ready_count=ready_count,
            warning_count=warning_count,
            blocked_count=blocked_count,
        ),
        items=items,
        suggestions=suggestions,
        runtime_values={
            "opening_hook_texts": [suggestion.text for suggestion in suggestions],
            "intensity": payload.intensity,
        },
        output_preset_id=payload.output_preset_id,
        name_prefix=payload.name_prefix,
        template_id=template.id,
        template_name=template.name,
        warnings=plan_warnings,
    )


def strong_opening_template(db: Session) -> Template:
    template = db.scalar(
        select(Template).where(Template.name == STRONG_OPENING_TEMPLATE_NAME)
    )
    if template is None:
        raise HTTPException(
            status_code=500,
            detail="强开场内置模板尚未初始化，请重启后端或重新执行内置模板同步。",
        )
    return template


def strong_opening_suggestions_for_payload(
    payload: StrongOpeningExpansionRequest,
    asset: Asset,
) -> tuple[List[OpeningCopySuggestion], List[str]]:
    warnings: List[str] = []
    if payload.opening_texts:
        suggestions = [
            OpeningCopySuggestion(
                id=suggestion_id(text),
                text=text,
                angle="custom",
                source="user",
                risk_level="manual_review",
                length_level="short" if len(text) <= 18 else "medium",
            )
            for text in normalized_opening_texts(payload.opening_texts)
        ]
    elif payload.suggestions:
        suggestions = [
            suggestion.model_copy(update={"text": text})
            for suggestion in payload.suggestions
            for text in normalized_opening_texts([suggestion.text])
        ]
    else:
        suggestions, warnings = opening_copy_suggestions(
            payload,
            settings=settings,
            asset_filename=asset.original_filename,
        )
    if not suggestions:
        raise HTTPException(status_code=400, detail="至少需要一条强开场文字。")
    return suggestions[:120], warnings


def normalized_opening_texts(values: List[str]) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()
    for value in values:
        text = trim_copy(" ".join(str(value or "").strip().split()), 36)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def strong_opening_task_params(
    payload: StrongOpeningExpansionRequest,
    suggestion: OpeningCopySuggestion,
    variant_index: int,
    variant_count: int,
    preflight: Optional[StrongOpeningExpansionPreflightRead],
) -> dict:
    output_preset_id = payload.output_preset_id or "vertical_9_16_cover"
    params = {
        "runtime_values": {
            "opening_hook_text": suggestion.text,
            "output_preset_id": output_preset_id,
        },
        "output_preset_id": output_preset_id,
        "expansion": {
            "plan_id": "strong_opening",
            "variant_index": variant_index,
            "variant_count": variant_count,
            "intensity": payload.intensity,
            "copy_angle": suggestion.angle,
            "copy_source": suggestion.source,
            "copy_id": suggestion.id,
        },
    }
    if preflight is not None:
        params["production_run_preflight"] = preflight.model_dump(exclude_none=True)
    return params


def strong_opening_task_name(
    run_name: str,
    index: int,
    suggestion: OpeningCopySuggestion,
) -> str:
    safe_text = " ".join(suggestion.text.split())
    if len(safe_text) > 24:
        safe_text = f"{safe_text[:23]}…"
    return f"{run_name} - 强开场 {index:02d} - {safe_text}"


@router.post("/production-runs/preflight", response_model=ProductionRunPreflightRead)
def preflight_production_run(
    payload: ProductionRunPreflightRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ProductionRunPreflightRead:
    user = optional_user_from_request(request, db)
    return build_production_run_preflight(
        db=db,
        payload=payload,
        user_id=user.id if user else None,
    )


@router.post("/production-runs/enqueue", response_model=List[GenerationTaskRead])
def enqueue_production_run(
    payload: ProductionRunEnqueueRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> List[GenerationTaskRead]:
    user = optional_user_from_request(request, db)
    preflight = build_production_run_preflight(
        db=db,
        payload=payload,
        user_id=user.id if user else None,
    )
    if payload.preflight_token and payload.preflight_token != preflight.preflight_token:
        raise HTTPException(status_code=400, detail="Preflight token does not match current plan")
    if preflight.summary.blocked_count:
        raise HTTPException(
            status_code=400,
            detail="这批任务还不能入队：请先处理预检中的缺失素材或必填参数。",
        )
    tasks = create_matrix_tasks(
        db=db,
        payload=payload,
        user_id=user.id if user else None,
        preflight=preflight,
    )
    for task in tasks:
        mark_task_progress(
            db=db,
            task=task,
            status=TaskStatus.WAITING.value,
            progress_percent=0,
            progress_message="Waiting in render queue",
            commit=False,
        )
    db.commit()
    for task in tasks:
        db.refresh(task)
        task_queue.enqueue(task.id, run_queued_task_pipeline)
    return tasks


def build_production_run_preflight(
    db: Session,
    payload: ProductionRunPreflightRequest,
    user_id: Optional[int],
) -> ProductionRunPreflightRead:
    if not payload.asset_ids:
        raise HTTPException(status_code=400, detail="至少选择一个视频。")
    if not payload.template_ids:
        raise HTTPException(status_code=400, detail="至少选择一个模板。")
    assets = ordered_assets(db, payload.asset_ids)
    templates = ordered_templates(db, payload.template_ids)
    items: List[VariantPreflightItem] = []
    for asset in assets:
        for template in templates:
            params_json = production_run_task_params(payload)
            task = GenerationTask(
                name="preflight",
                user_id=user_id,
                asset_id=asset.id,
                template_id=template.id,
                template=template,
                params_json=params_json,
            )
            spec = template_spec_for_task(task)
            warnings = template_warnings(spec)
            missing_fields: List[str] = []
            operation_labels: List[str] = []
            if (template.json_spec or {}).get("schema_version") == 3:
                template_v3 = TemplateSpecV3.model_validate(template.json_spec or {})
                missing_fields = v3_missing_runtime_fields(
                    template_v3,
                    payload.runtime_values,
                )
                operation_labels = v3_operation_labels(template_v3)
                if template_v3.input_requirements.min_seed_duration_seconds and (
                    asset.duration_seconds or 0
                ) < template_v3.input_requirements.min_seed_duration_seconds:
                    warnings.append("视频时长低于模板建议的最小时长。")
            music_plan = None
            if spec.music.track_id is not None:
                try:
                    music_plan = music_plan_for_task(db=db, task=task, template_spec=spec)
                except HTTPException as exc:
                    warnings.append(str(exc.detail))
            transformations = spec.transformations.model_dump(exclude_none=True)
            estimated_clip_count = estimate_clip_count(
                asset_duration=asset.duration_seconds,
                segment_seconds=spec.segments.segment_seconds,
                requested_count=spec.selection.count,
                max_duration=spec.selection.max_total_duration,
            )
            estimated_duration = (
                min(asset.duration_seconds or 0, estimated_clip_count * spec.segments.segment_seconds)
                if asset.duration_seconds
                else None
            )
            if operation_labels:
                warnings.extend([f"将执行：{', '.join(operation_labels)}"])
            items.append(
                VariantPreflightItem(
                    asset_id=asset.id,
                    asset_filename=asset.original_filename,
                    template_id=template.id,
                    template_name=template.name,
                    status="blocked" if missing_fields else ("warning" if warnings else "ready"),
                    title=spec.creative_goal.title,
                    estimated_clip_count=estimated_clip_count,
                    estimated_duration_seconds=estimated_duration,
                    output_width=spec.output.width,
                    output_height=spec.output.height,
                    output_fps=spec.output.fps,
                    fit=spec.layout.fit,
                    cover_region_count=len(transformations.get("cover_regions") or []),
                    text_overlay_count=len(transformations.get("text_overlays") or []),
                    playback_speed=transformations.get("playback_speed"),
                    mute_audio=bool(transformations.get("mute_audio")),
                    music_track_id=music_plan.get("track_id") if music_plan else None,
                    music_title=music_plan.get("title") if music_plan else None,
                    music_mode=music_plan.get("mode") if music_plan else None,
                    music_volume=music_plan.get("volume") if music_plan else None,
                    music_loop=bool(music_plan.get("loop")) if music_plan else False,
                    warnings=warnings,
                    missing_fields=missing_fields,
                )
            )
    ready_count = len([item for item in items if item.status == "ready"])
    warning_count = len([item for item in items if item.status == "warning"])
    blocked_count = len([item for item in items if item.status == "blocked"])
    token_payload = {
        "asset_ids": payload.asset_ids,
        "template_ids": payload.template_ids,
        "runtime_values": payload.runtime_values,
        "output_preset_id": payload.output_preset_id,
        "name_prefix": payload.name_prefix,
    }
    return ProductionRunPreflightRead(
        preflight_token=hashlib.sha256(
            json.dumps(token_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        summary=ProductionRunPreflightSummary(
            asset_count=len(assets),
            template_count=len(templates),
            task_count=len(items),
            ready_count=ready_count,
            warning_count=warning_count,
            blocked_count=blocked_count,
        ),
        items=items,
        runtime_values=payload.runtime_values,
        output_preset_id=payload.output_preset_id,
        name_prefix=payload.name_prefix,
    )


def create_matrix_tasks(
    db: Session,
    payload: ProductionRunEnqueueRequest,
    user_id: Optional[int],
    preflight: ProductionRunPreflightRead,
) -> List[GenerationTask]:
    assets = ordered_assets(db, payload.asset_ids)
    templates = ordered_templates(db, payload.template_ids)
    primary_asset = assets[0]
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    run_name = f"{timestamp} {' '.join(payload.name_prefix.split()) or 'production-batch'}"
    production_run = ProductionRun(
        asset_id=primary_asset.id,
        name=run_name,
        name_prefix=" ".join(payload.name_prefix.split()) or "production-batch",
    )
    db.add(production_run)
    db.flush()
    tasks: List[GenerationTask] = []
    params_json = {
        **production_run_task_params(payload),
        "production_run_preflight": preflight.model_dump(exclude_none=True),
    }
    for asset in assets:
        for template in templates:
            task = GenerationTask(
                name=f"{run_name} - {asset.original_filename} - {template.name}",
                user_id=user_id,
                production_run_id=production_run.id,
                revision_number=1,
                asset_id=asset.id,
                template_id=template.id,
                params_json=params_json,
                status=TaskStatus.QUEUED.value,
            )
            db.add(task)
            tasks.append(task)
    db.commit()
    for task in tasks:
        db.refresh(task)
        record_task_event(
            db=db,
            task=task,
            status=task.status,
            progress_percent=task.progress_percent,
            message="Task created from production matrix",
            commit=False,
        )
    db.commit()
    return tasks


def production_run_task_params(payload: ProductionRunPreflightRequest) -> dict:
    return {
        "runtime_values": {
            **payload.runtime_values,
            **({"output_preset_id": payload.output_preset_id} if payload.output_preset_id else {}),
        },
        "output_preset_id": payload.output_preset_id,
    }


def ordered_assets(db: Session, asset_ids: List[int]) -> List[Asset]:
    assets = list(db.scalars(select(Asset).where(Asset.id.in_(asset_ids))))
    found_ids = {asset.id for asset in assets}
    missing_ids = [asset_id for asset_id in asset_ids if asset_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Assets not found: {missing_ids}")
    return sorted(assets, key=lambda asset: asset_ids.index(asset.id))


def ordered_templates(db: Session, template_ids: List[int]) -> List[Template]:
    templates = list(db.scalars(select(Template).where(Template.id.in_(template_ids))))
    found_ids = {template.id for template in templates}
    missing_ids = [template_id for template_id in template_ids if template_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Templates not found: {missing_ids}")
    return sorted(templates, key=lambda template: template_ids.index(template.id))


@router.get("/tasks", response_model=List[GenerationTaskRead])
def list_tasks(request: Request, db: Session = Depends(get_db)) -> List[GenerationTaskRead]:
    query = select(GenerationTask)
    user = optional_user_from_request(request, db)
    if user is not None:
        query = query.where(GenerationTask.user_id == user.id)
    return list(db.scalars(query.order_by(GenerationTask.created_at.desc())))


@router.get("/tasks/{task_id}/events", response_model=List[TaskEventRead])
def list_task_events(
    task_id: int, request: Request, db: Session = Depends(get_db)
) -> List[TaskEventRead]:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_task_access(task, request, db)
    return list(
        db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .order_by(TaskEvent.created_at)
        )
    )


@router.post("/tasks/{task_id}/render-plan", response_model=RenderPlanRead)
def build_render_plan(
    task_id: int, request: Request, db: Session = Depends(get_db)
) -> RenderPlanRead:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_task_access(task, request, db)
    return build_render_plan_for_task(db=db, task_id=task_id)


def build_render_plan_for_task(db: Session, task_id: int) -> RenderPlan:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    segments = list(
        db.scalars(
            select(Segment)
            .where(Segment.asset_id == task.asset_id)
            .where(Segment.status == SegmentStatus.READY.value)
            .order_by(Segment.segment_index)
        )
    )
    if not segments:
        raise HTTPException(status_code=400, detail="Asset has no ready segments")

    template_spec = template_spec_for_task(task)
    validate_render_spec(template_spec)
    selected_segments = select_segments_for_template(segments, template_spec)
    if not selected_segments:
        raise HTTPException(status_code=400, detail="Template selected no segments")
    music_plan = music_plan_for_task(db=db, task=task, template_spec=template_spec)
    ai_asset_slots = media_slots_for_task(db=db, task=task, warnings=[])
    render_clips = compose_render_clips(
        selected_segments=selected_segments,
        ai_asset_slots=ai_asset_slots,
    )

    task.status = TaskStatus.PLANNING.value
    plan_json = {
        "type": template_spec.type,
        "task_id": task.id,
        "asset_id": task.asset_id,
        "template_id": task.template_id,
        "template": {
            "name": task.template.name,
            "version": task.template.version,
        },
        "recipe": {
            "schema_version": (task.template.json_spec or {}).get("schema_version"),
            "recipe_id": (task.template.json_spec or {}).get("recipe_id"),
            "template_id": (task.template.json_spec or {}).get("template_id"),
            "blueprint_id": ((task.template.json_spec or {}).get("blueprint") or {}).get(
                "blueprint_id"
            ),
            "render_preset_id": (
                (task.template.json_spec or {}).get("render_preset") or {}
            ).get("preset_id"),
            "style_pack_id": ((task.template.json_spec or {}).get("style_pack") or {}).get(
                "style_pack_id"
            ),
            "copy_pack_id": ((task.template.json_spec or {}).get("copy_pack") or {}).get(
                "copy_pack_id"
            ),
            "slot_bindings": (task.template.json_spec or {}).get("slot_bindings", {}),
        },
        "creative_goal": template_spec.creative_goal.model_dump(exclude_none=True),
        "production_contract": template_spec.production_contract.model_dump(
            exclude_none=True
        ),
        "clips": render_clips,
        "ai_asset_slots": ai_asset_slots,
        "output": {
            "path": str(task_output_path(task.id)),
            "format": template_spec.output.format,
            "width": template_spec.output.width,
            "height": template_spec.output.height,
            "fps": template_spec.output.fps,
        },
        "layout": {"fit": template_spec.layout.fit},
        "selection": template_spec.selection.model_dump(exclude_none=True),
        "music": music_plan,
        "transformations": template_spec.transformations.model_dump(exclude_none=True),
    }

    render_plan = task.render_plan
    if render_plan is None:
        render_plan = RenderPlan(
            task_id=task.id,
            plan_json=plan_json,
            status=RenderPlanStatus.READY.value,
        )
        db.add(render_plan)
    else:
        render_plan.plan_json = plan_json
        render_plan.status = RenderPlanStatus.READY.value
    task.status = TaskStatus.QUEUED.value
    db.commit()
    db.refresh(render_plan)
    return render_plan


def music_plan_for_task(
    db: Session, task: GenerationTask, template_spec: CompiledTemplateSpec
) -> Optional[dict]:
    if template_spec.music.track_id is None:
        return None
    track = db.get(MusicTrack, template_spec.music.track_id)
    if track is None or not track.is_active:
        raise HTTPException(status_code=400, detail="Music track not found")
    if track.scope != "system" and track.user_id != task.user_id:
        raise HTTPException(status_code=403, detail="Music track is private")
    if not track.file_path or not Path(track.file_path).exists():
        raise HTTPException(status_code=400, detail="Music file is missing")
    return {
        "mode": template_spec.music.mode,
        "track_id": track.id,
        "title": track.title,
        "scope": track.scope,
        "file_path": track.file_path,
        "volume": template_spec.music.volume,
        "loop": template_spec.music.loop,
    }


def ai_asset_slot_bindings(recipe: TemplateSpec) -> dict:
    return {
        slot: binding
        for slot, binding in recipe.slot_bindings.items()
        if binding.source_type == "ai_asset"
    }


def select_ai_asset_slots_for_recipe(
    db: Session,
    task: GenerationTask,
    recipe: TemplateSpec,
    warnings: List[str],
) -> List[dict]:
    selected_slots = []
    blueprint_slots = {slot.slot: slot for slot in recipe.blueprint.slots}
    for slot_name, binding in ai_asset_slot_bindings(recipe).items():
        asset = find_ai_asset_for_slot(db=db, task=task, binding=binding)
        if asset is None:
            blueprint_slot = blueprint_slots.get(slot_name)
            if not binding.optional and not (blueprint_slot and blueprint_slot.optional):
                warnings.append(f"AI asset slot '{slot_name}' has no matching ready asset.")
            continue
        selected_slots.append(
            {
                "slot": slot_name,
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "title": asset.title,
                "scope": asset.scope,
                "provider": asset.provider,
                "tags": [tag.tag for tag in asset.tags],
                "duration_seconds": asset.duration_seconds,
                "source_path": asset.file_path,
                "position": slot_position(slot_name),
            }
        )
    return selected_slots


def media_slots_for_task(db: Session, task: GenerationTask, warnings: List[str]) -> List[dict]:
    json_spec = task.template.json_spec or {}
    if json_spec.get("schema_version") != 3:
        recipe = TemplateSpec.model_validate(json_spec)
        return select_ai_asset_slots_for_recipe(
            db=db,
            task=task,
            recipe=recipe,
            warnings=warnings,
        )

    template = TemplateSpecV3.model_validate(json_spec)
    slot_names = {
        operation.slot
        for operation in template.operations
        if operation.type in {"prepend_clip", "append_clip"} and operation.slot
    }
    selected_slots = []
    for slot_name, asset_id in v3_runtime_asset_ids(task.params_json or {}, slot_names).items():
        asset = db.get(AIAsset, asset_id)
        if asset is None:
            warnings.append(f"素材槽位“{slot_name}”指定的片段不存在。")
            continue
        if asset.asset_kind != AIAssetKind.VIDEO.value or asset.status != AIAssetStatus.READY.value:
            warnings.append(f"素材槽位“{slot_name}”不是可用视频片段。")
            continue
        selected_slots.append(
            {
                "slot": slot_name,
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "title": asset.title,
                "scope": asset.scope,
                "provider": asset.provider,
                "tags": [tag.tag for tag in asset.tags],
                "duration_seconds": asset.duration_seconds,
                "source_path": asset.file_path,
                "position": slot_position(slot_name),
            }
        )
    return selected_slots


def find_ai_asset_for_slot(db: Session, task: GenerationTask, binding) -> Optional[AIAsset]:
    if binding.asset_id is not None:
        asset = db.get(AIAsset, binding.asset_id)
        if asset is None:
            return None
        if asset.status != AIAssetStatus.READY.value or asset.asset_kind != AIAssetKind.VIDEO.value:
            return None
        if task.user_id is None and asset.scope != "system":
            return None
        if task.user_id is not None and asset.scope != "system" and asset.user_id != task.user_id:
            return None
        return asset

    query = select(AIAsset).where(
        AIAsset.status == AIAssetStatus.READY.value,
        AIAsset.asset_kind == AIAssetKind.VIDEO.value,
    )
    if task.user_id is None:
        query = query.where(AIAsset.scope == "system")
    else:
        query = query.where((AIAsset.scope == "system") | (AIAsset.user_id == task.user_id))
    if binding.asset_type:
        query = query.where(AIAsset.asset_type == binding.asset_type)
    if binding.duration:
        query = query.where(
            (AIAsset.duration_seconds.is_(None))
            | (
                (AIAsset.duration_seconds >= binding.duration[0])
                & (AIAsset.duration_seconds <= binding.duration[1])
            )
        )
    for tag in normalize_ai_asset_tags(binding.tags):
        query = query.where(AIAsset.tags.any(AIAssetTag.tag == tag))
    return db.scalar(
        query.order_by(
            AIAsset.usage_count.asc(),
            AIAsset.created_at.desc(),
        )
    )


def slot_position(slot_name: str) -> str:
    if slot_name in {"hook", "intro", "opening"}:
        return "prefix"
    return "suffix"


def compose_render_clips(
    selected_segments: List[Segment], ai_asset_slots: List[dict]
) -> List[dict]:
    source_clips = [
        {
            "source_type": "source_segment",
            "segment_id": segment.id,
            "source_path": segment.file_path,
            "start_time": segment.start_time,
            "duration_seconds": segment.duration_seconds,
        }
        for segment in selected_segments
    ]
    ai_clips = [
        {
            "source_type": "ai_asset",
            "slot": slot["slot"],
            "asset_id": slot["asset_id"],
            "source_path": slot["source_path"],
            "start_time": 0,
            "duration_seconds": slot.get("duration_seconds"),
        }
        for slot in ai_asset_slots
    ]
    prefix = [clip for clip in ai_clips if clip.get("slot") in {"hook", "intro", "opening"}]
    suffix = [clip for clip in ai_clips if clip not in prefix]
    return [*prefix, *source_clips, *suffix]


@router.post("/tasks/{task_id}/render", response_model=OutputVideoRead)
def render_task(
    task_id: int, request: Request, db: Session = Depends(get_db)
) -> OutputVideoRead:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_task_access(task, request, db)
    return render_task_output(db=db, task_id=task_id)


@router.post("/tasks/{task_id}/enqueue", response_model=GenerationTaskRead)
def enqueue_task(
    task_id: int, request: Request, db: Session = Depends(get_db)
) -> GenerationTaskRead:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_task_access(task, request, db)
    mark_task_progress(
        db=db,
        task=task,
        status=TaskStatus.WAITING.value,
        progress_percent=0,
        progress_message="Waiting in render queue",
        commit=False,
    )
    db.commit()
    db.refresh(task)
    task_queue.enqueue(task.id, run_queued_task_pipeline)
    return task


def render_task_output(db: Session, task_id: int) -> OutputVideo:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.render_plan is None:
        raise HTTPException(status_code=400, detail="Task has no render plan")

    mark_task_progress(
        db=db,
        task=task,
        status=TaskStatus.RENDERING.value,
        progress_percent=max(task.progress_percent or 0, 70),
        progress_message="Rendering output video",
        commit=False,
    )
    task.render_plan.status = RenderPlanStatus.RENDERING.value
    db.commit()

    segment_paths = [
        Path(clip["source_path"]) for clip in task.render_plan.plan_json.get("clips", [])
    ]
    output_spec = task.render_plan.plan_json.get("output", {})
    layout_spec = task.render_plan.plan_json.get("layout", {})
    transformations_spec = task.render_plan.plan_json.get("transformations", {})
    music_spec = task.render_plan.plan_json.get("music")
    output_path = task_output_path(task.id)
    try:
        if should_render_with_filters(output_spec, layout_spec, transformations_spec):
            render_kwargs = {
                "segment_paths": segment_paths,
                "concat_file": concat_list_path(task.id),
                "output_path": output_path,
                "width": output_spec.get("width"),
                "height": output_spec.get("height"),
                "fps": output_spec.get("fps"),
                "fit": layout_spec.get("fit", "original"),
            }
            if has_transformations(transformations_spec):
                render_kwargs["transformations"] = transformations_spec
            render_timeline(
                **render_kwargs,
            )
        else:
            render_concat(segment_paths, concat_list_path(task.id), output_path)
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise FFmpegError("Renderer completed but did not create a non-empty output file")
        metadata = probe_media(output_path)
        if music_spec:
            music_output_path = output_path.with_name(f"{output_path.stem}-music{output_path.suffix}")
            replace_audio_track(
                video_path=output_path,
                music_path=Path(music_spec["file_path"]),
                output_path=music_output_path,
                duration_seconds=metadata.get("duration_seconds"),
                volume=music_spec.get("volume", 1.0),
                loop=music_spec.get("loop", True),
            )
            music_output_path.replace(output_path)
            metadata = probe_media(output_path)
        if output_path.stat().st_size >= 1024:
            validate_output_metadata(metadata=metadata, output_spec=output_spec)
    except FFmpegError as exc:
        task.status = TaskStatus.FAILED.value
        task.error_message = str(exc)
        task.render_plan.status = RenderPlanStatus.FAILED.value
        failed_output = OutputVideo(
            task_id=task.id,
            render_plan_id=task.render_plan.id,
            filename=output_path.name,
            file_path=str(output_path),
            file_size_bytes=output_path.stat().st_size if output_path.exists() else None,
            status=OutputVideoStatus.FAILED.value,
            review_status=ReviewStatus.PENDING_REVIEW.value,
            review_notes=str(exc),
        )
        db.add(failed_output)
        record_task_event(
            db=db,
            task=task,
            status=TaskStatus.FAILED.value,
            progress_percent=max(task.progress_percent or 0, 1),
            message="Render failed",
            error_message=str(exc),
            commit=False,
        )
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    output = OutputVideo(
        task_id=task.id,
        render_plan_id=task.render_plan.id,
        filename=output_path.name,
        file_path=str(output_path),
        duration_seconds=metadata["duration_seconds"],
        width=metadata["width"],
        height=metadata["height"],
        fps=metadata["fps"],
        file_size_bytes=output_path.stat().st_size,
        status=OutputVideoStatus.READY.value,
        review_status=ReviewStatus.PENDING_REVIEW.value,
    )
    for slot in task.render_plan.plan_json.get("ai_asset_slots", []):
        asset_id = slot.get("asset_id")
        if asset_id is None:
            continue
        ai_asset = db.get(AIAsset, asset_id)
        if ai_asset is not None:
            ai_asset.usage_count += 1
    mark_task_progress(
        db=db,
        task=task,
        status=TaskStatus.COMPLETED.value,
        progress_percent=100,
        progress_message="Output ready for review",
        commit=False,
    )
    task.render_plan.status = RenderPlanStatus.RENDERED.value
    db.add(output)
    db.commit()
    db.refresh(output)
    return output


def mark_task_progress(
    db: Session,
    task: GenerationTask,
    status: Optional[str],
    progress_percent: int,
    progress_message: str,
    commit: bool = True,
) -> None:
    if status is not None:
        task.status = status
    task.progress_percent = max(0, min(100, progress_percent))
    task.progress_message = progress_message
    record_task_event(
        db=db,
        task=task,
        status=task.status,
        progress_percent=task.progress_percent,
        message=progress_message,
        error_message=task.error_message,
        commit=False,
    )
    if commit:
        db.commit()


def record_task_event(
    db: Session,
    task: GenerationTask,
    status: str,
    progress_percent: int,
    message: Optional[str],
    error_message: Optional[str] = None,
    commit: bool = True,
) -> None:
    db.add(
        TaskEvent(
            task_id=task.id,
            status=status,
            progress_percent=max(0, min(100, progress_percent)),
            message=message,
            error_message=error_message,
        )
    )
    if commit:
        db.commit()


def should_render_with_filters(
    output_spec: dict, layout_spec: dict, transformations_spec: Optional[dict] = None
) -> bool:
    return bool(
        output_spec.get("width")
        or output_spec.get("height")
        or output_spec.get("fps")
        or layout_spec.get("fit") in ("cover", "contain")
        or has_transformations(transformations_spec)
    )


def has_transformations(transformations_spec: Optional[dict] = None) -> bool:
    neutral_values = {
        "orientation": "normal",
        "visual_style": "natural",
        "finishing_style": "none",
        "motion_style": "none",
        "transition_style": "hard_cut",
        "texture_style": "none",
    }
    for key, value in (transformations_spec or {}).items():
        if key in neutral_values and value == neutral_values[key]:
            continue
        if value is None or value is False:
            continue
        if isinstance(value, (list, dict, str)) and not value:
            continue
        return True
    return False


@router.post("/tasks/{task_id}/run", response_model=TaskRunResponse)
def run_task_pipeline(
    task_id: int,
    request: Request,
    payload: Optional[TaskRunRequest] = None,
    db: Session = Depends(get_db),
) -> TaskRunResponse:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_task_access(task, request, db)
    return run_task_pipeline_for_task(db=db, task=task, payload=payload)


def run_task_pipeline_for_task(
    db: Session, task: GenerationTask, payload: Optional[TaskRunRequest] = None
) -> TaskRunResponse:
    template_spec = template_spec_for_task(task)
    segment_seconds = (
        payload.segment_seconds
        if payload is not None and payload.segment_seconds is not None
        else template_spec.segments.segment_seconds
    )
    mark_task_progress(
        db=db,
        task=task,
        status=TaskStatus.SEGMENTING.value,
        progress_percent=10,
        progress_message="Segmenting source video",
    )
    segments = segment_asset_for_task(
        db=db, asset_id=task.asset_id, segment_seconds=segment_seconds
    )
    mark_task_progress(
        db=db,
        task=task,
        status=TaskStatus.PLANNING.value,
        progress_percent=45,
        progress_message="Building render plan",
    )
    render_plan = build_render_plan_for_task(db=db, task_id=task.id)
    db.refresh(task)
    mark_task_progress(
        db=db,
        task=task,
        status=TaskStatus.RENDERING.value,
        progress_percent=70,
        progress_message="Rendering output video",
    )
    output = render_task_output(db=db, task_id=task.id)
    db.refresh(task)
    return TaskRunResponse(
        task=task,
        segments=segments,
        render_plan=render_plan,
        output=output,
    )


def run_queued_task_pipeline(task_id: int) -> None:
    with SessionLocal() as db:
        task = db.get(GenerationTask, task_id)
        if task is None:
            return
        try:
            run_task_pipeline_for_task(db=db, task=task, payload=None)
        except Exception as exc:
            db.rollback()
            task = db.get(GenerationTask, task_id)
            if task is None:
                return
            task.status = TaskStatus.FAILED.value
            task.progress_percent = max(task.progress_percent or 0, 1)
            task.progress_message = "Task failed"
            task.error_message = str(exc)
            record_task_event(
                db=db,
                task=task,
                status=TaskStatus.FAILED.value,
                progress_percent=task.progress_percent,
                message="Task failed",
                error_message=str(exc),
                commit=False,
            )
            db.commit()


def template_spec_for_task(task: GenerationTask) -> CompiledTemplateSpec:
    return compile_template_json_spec(task.template.json_spec or {}, task.params_json or {})


def compile_template_json_spec(
    json_spec: dict, params_json: Optional[dict] = None
) -> CompiledTemplateSpec:
    if json_spec.get("schema_version") == 3:
        template = TemplateSpecV3.model_validate(json_spec)
        return compile_template_v3_spec(template, params_json or {})
    recipe = TemplateSpec.model_validate(json_spec)
    return compile_template_spec(recipe, params_json or {})


def validate_render_spec(spec: CompiledTemplateSpec) -> None:
    if spec.output.format != "mp4":
        raise HTTPException(status_code=400, detail="Only mp4 output is supported")
    if (spec.output.width is None) != (spec.output.height is None):
        raise HTTPException(
            status_code=400,
            detail="output.width and output.height must be set together",
        )
    if spec.output.width is not None and spec.output.width % 2 != 0:
        raise HTTPException(status_code=400, detail="output.width must be even")
    if spec.output.height is not None and spec.output.height % 2 != 0:
        raise HTTPException(status_code=400, detail="output.height must be even")
    if spec.layout.fit not in {"original", "cover", "contain"}:
        raise HTTPException(status_code=400, detail=f"Unsupported fit mode: {spec.layout.fit}")


def estimate_clip_count(
    asset_duration: Optional[float],
    segment_seconds: float,
    requested_count: Optional[int],
    max_duration: Optional[float],
) -> int:
    if requested_count is not None:
        return requested_count
    if max_duration is not None:
        return max(1, int(max_duration // segment_seconds))
    if asset_duration:
        return max(1, int(asset_duration // segment_seconds))
    return 1


def validate_output_metadata(metadata: dict, output_spec: dict) -> None:
    expected_width = output_spec.get("width")
    expected_height = output_spec.get("height")
    expected_fps = output_spec.get("fps")
    if expected_width and metadata.get("width") != expected_width:
        raise FFmpegError(
            f"Rendered width {metadata.get('width')} did not match expected {expected_width}"
        )
    if expected_height and metadata.get("height") != expected_height:
        raise FFmpegError(
            f"Rendered height {metadata.get('height')} did not match expected {expected_height}"
        )
    actual_fps = metadata.get("fps")
    if expected_fps and actual_fps and abs(float(actual_fps) - float(expected_fps)) > 1.0:
        raise FFmpegError(f"Rendered fps {actual_fps:.2f} did not match expected {expected_fps}")


def select_segments_for_template(
    segments: List[Segment], template_spec: CompiledTemplateSpec
) -> List[Segment]:
    selection = template_spec.selection
    if selection.mode in ("all", "all_ready_segments"):
        selected = list(segments)
    elif selection.mode == "first_n":
        selected = list(segments[: selection.count or len(segments)])
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported template selection mode: {selection.mode}",
        )

    if selection.max_total_duration is None:
        return selected

    limited = []
    total_duration = 0.0
    for segment in selected:
        if total_duration + segment.duration_seconds > selection.max_total_duration:
            break
        limited.append(segment)
        total_duration += segment.duration_seconds
    return limited


@router.get("/outputs", response_model=List[OutputVideoRead])
def list_outputs(request: Request, db: Session = Depends(get_db)) -> List[OutputVideoRead]:
    query = select(OutputVideo).join(GenerationTask)
    user = optional_user_from_request(request, db)
    if user is not None:
        query = query.where(GenerationTask.user_id == user.id)
    return list(db.scalars(query.order_by(OutputVideo.created_at.desc())))


@router.get("/outputs/review", response_model=List[OutputReviewRead])
def list_outputs_for_review(
    request: Request, db: Session = Depends(get_db)
) -> List[OutputReviewRead]:
    query = select(OutputVideo).join(GenerationTask)
    user = optional_user_from_request(request, db)
    if user is not None:
        query = query.where(GenerationTask.user_id == user.id)
    outputs = list(db.scalars(query.order_by(OutputVideo.created_at.desc())))
    return [output_review_payload(output) for output in outputs]


@router.get("/outputs/{output_id}/file")
def get_output_file(
    output_id: int, request: Request, db: Session = Depends(get_db)
) -> FileResponse:
    output = db.get(OutputVideo, output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Output video not found")
    ensure_output_access(output, request, db)
    path = Path(output.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(path, media_type="video/mp4", filename=output.filename)


def approved_outputs_for_production_run(
    db: Session, production_run_id: int, user_id: Optional[int] = None
) -> List[OutputVideo]:
    query = (
        select(OutputVideo)
        .join(GenerationTask)
        .where(GenerationTask.production_run_id == production_run_id)
        .where(OutputVideo.status == OutputVideoStatus.READY.value)
        .where(OutputVideo.review_status == ReviewStatus.APPROVED.value)
        .order_by(OutputVideo.created_at.asc(), OutputVideo.id.asc())
    )
    if user_id is not None:
        query = query.where(GenerationTask.user_id == user_id)
    return list(db.scalars(query))


def production_run_package_estimate(
    db: Session, production_run: ProductionRun, user_id: Optional[int] = None
) -> ProductionRunPackageEstimate:
    seed_path = Path(production_run.asset.file_path)
    missing_files = []
    seed_size = 0
    if seed_path.exists():
        seed_size = seed_path.stat().st_size
    else:
        missing_files.append(production_run.asset.original_filename)

    approved_outputs = approved_outputs_for_production_run(db, production_run.id, user_id)
    approved_size = 0
    for output in approved_outputs:
        output_path = Path(output.file_path)
        if output_path.exists():
            approved_size += output_path.stat().st_size
        else:
            missing_files.append(output.filename)

    return ProductionRunPackageEstimate(
        production_run_id=production_run.id,
        package_name=safe_archive_name(
            f"flashcutter-run-{production_run.id}-{production_run.name}"
        ),
        seed_filename=production_run.asset.original_filename,
        seed_size_bytes=seed_size,
        approved_output_count=len(approved_outputs),
        approved_output_size_bytes=approved_size,
        total_size_bytes=seed_size + approved_size,
        missing_files=missing_files,
    )


def safe_archive_name(value: str) -> str:
    normalized = re.sub(r"[^\w.\-]+", "_", value.strip(), flags=re.UNICODE)
    normalized = normalized.strip("._")
    return normalized[:180] or "flashcutter-package"


@router.get(
    "/production-runs/{production_run_id}/package/estimate",
    response_model=ProductionRunPackageEstimate,
)
def estimate_production_run_package(
    production_run_id: int, request: Request, db: Session = Depends(get_db)
) -> ProductionRunPackageEstimate:
    production_run = db.get(ProductionRun, production_run_id)
    if production_run is None:
        raise HTTPException(status_code=404, detail="Production run not found")
    user = ensure_production_run_access(production_run, request, db)
    return production_run_package_estimate(
        db=db,
        production_run=production_run,
        user_id=user.id if user else None,
    )


@router.get("/production-runs/{production_run_id}/package")
def download_production_run_package(
    production_run_id: int, request: Request, db: Session = Depends(get_db)
) -> FileResponse:
    production_run = db.get(ProductionRun, production_run_id)
    if production_run is None:
        raise HTTPException(status_code=404, detail="Production run not found")
    user = ensure_production_run_access(production_run, request, db)
    user_id = user.id if user else None
    estimate = production_run_package_estimate(
        db=db, production_run=production_run, user_id=user_id
    )
    if estimate.approved_output_count == 0:
        raise HTTPException(status_code=400, detail="Production run has no approved videos")

    package_dir = storage_root() / "temp" / "packages"
    package_dir.mkdir(parents=True, exist_ok=True)
    package_path = package_dir / f"{estimate.package_name}.zip"
    approved_outputs = approved_outputs_for_production_run(db, production_run.id, user_id)
    seed_path = Path(production_run.asset.file_path)
    if not seed_path.exists():
        raise HTTPException(status_code=404, detail="Seed video file not found")

    review_rows = []
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(seed_path, f"seed/{safe_archive_name(production_run.asset.original_filename)}")
        for output in approved_outputs:
            output_path = Path(output.file_path)
            if not output_path.exists():
                continue
            filename = safe_archive_name(
                f"task-{output.task_id}-{output.task.template.name}-{output.filename}"
            )
            archive.write(output_path, f"approved/{filename}")
            review_rows.append(
                {
                    "output_id": output.id,
                    "task_id": output.task_id,
                    "task_name": output.task.name,
                    "template_id": output.task.template_id,
                    "template_name": output.task.template.name,
                    "review_status": output.review_status,
                    "review_notes": output.review_notes or "",
                    "review_feedback": json.dumps(
                        output.review_feedback_json or {}, ensure_ascii=False
                    ),
                    "filename": filename,
                }
            )
        manifest = {
            "production_run_id": production_run.id,
            "production_run_name": production_run.name,
            "seed_filename": production_run.asset.original_filename,
            "approved_output_count": len(review_rows),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "safety_note": "Only approved videos are included. This package does not bypass platform review.",
            "outputs": review_rows,
        }
        archive.writestr(
            "metadata/manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=[
                "output_id",
                "task_id",
                "task_name",
                "template_id",
                "template_name",
                "review_status",
                "review_notes",
                "review_feedback",
                "filename",
            ],
        )
        writer.writeheader()
        writer.writerows(review_rows)
        archive.writestr("metadata/review_records.csv", csv_buffer.getvalue())

    return FileResponse(
        package_path,
        media_type="application/zip",
        filename=f"{estimate.package_name}.zip",
    )


@router.patch("/production-runs/{production_run_id}/status")
def update_production_run_status(
    production_run_id: int,
    payload: ProductionRunStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    production_run = db.get(ProductionRun, production_run_id)
    if production_run is None:
        raise HTTPException(status_code=404, detail="Production run not found")
    ensure_production_run_access(production_run, request, db)
    allowed_statuses = {
        ProductionRunStatus.IN_REVIEW.value,
        ProductionRunStatus.NEEDS_REVISION.value,
        ProductionRunStatus.APPROVED.value,
    }
    if payload.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid production run status. Expected one of: {sorted(allowed_statuses)}",
        )
    production_run.status = payload.status
    db.commit()
    db.refresh(production_run)
    return {
        "id": production_run.id,
        "status": production_run.status,
    }


@router.get("/assets/{asset_id}/outputs", response_model=List[OutputReviewRead])
def list_asset_outputs(
    asset_id: int, request: Request, db: Session = Depends(get_db)
) -> List[OutputReviewRead]:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    query = (
        select(OutputVideo)
        .join(GenerationTask)
        .where(GenerationTask.asset_id == asset_id)
        .order_by(OutputVideo.created_at.desc())
    )
    user = optional_user_from_request(request, db)
    if user is not None:
        query = query.where(GenerationTask.user_id == user.id)
    outputs = list(db.scalars(query))
    return [output_review_payload(output) for output in outputs]


@router.patch("/outputs/{output_id}/review", response_model=OutputReviewRead)
def update_output_review(
    output_id: int,
    payload: OutputReviewUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> OutputReviewRead:
    output = db.get(OutputVideo, output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Output video not found")
    ensure_output_access(output, request, db)

    valid_statuses = {status.value for status in ReviewStatus}
    if payload.review_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid review_status. Expected one of: {sorted(valid_statuses)}",
        )

    output.review_status = payload.review_status
    output.review_notes = payload.review_notes
    change_requests = [request.model_dump() for request in payload.change_requests]
    if not change_requests and payload.change_request:
        change_requests = [
            {
                "category": "other",
                "request": payload.change_request,
                "target": None,
                "priority": payload.priority,
            }
        ]
    output.review_feedback_json = {
        "reviewer_name": payload.reviewer_name,
        "change_request": payload.change_request,
        "change_requests": change_requests,
        "priority": payload.priority,
        "tags": payload.tags,
    }
    output.reviewed_at = datetime.utcnow()
    sync_production_run_status(output.task.production_run)
    db.commit()
    db.refresh(output)
    return output_review_payload(output)


def sync_production_run_status(production_run: Optional[ProductionRun]) -> None:
    if production_run is None or production_run.status in {
        ProductionRunStatus.ARCHIVED.value,
        ProductionRunStatus.NEEDS_REVISION.value,
    }:
        return
    outputs = [
        output
        for task in production_run.generation_tasks
        for output in task.output_videos
    ]
    if not outputs:
        production_run.status = ProductionRunStatus.IN_REVIEW.value
        return
    review_statuses = {output.review_status for output in outputs}
    if ReviewStatus.PENDING_REVIEW.value in review_statuses:
        production_run.status = ProductionRunStatus.IN_REVIEW.value
    elif review_statuses and review_statuses <= {
        ReviewStatus.APPROVED.value,
        ReviewStatus.NEEDS_CHANGES.value,
        ReviewStatus.DISCARDED.value,
        ReviewStatus.REJECTED.value,
    }:
        production_run.status = ProductionRunStatus.APPROVED.value
    else:
        production_run.status = ProductionRunStatus.IN_REVIEW.value


def output_review_payload(output: OutputVideo) -> OutputReviewRead:
    task = output.task
    asset = task.asset
    template = task.template
    return OutputReviewRead(
        output_id=output.id,
        asset_id=asset.id,
        asset_filename=asset.original_filename,
        production_run_id=task.production_run_id,
        production_run_name=task.production_run.name if task.production_run else None,
        production_run_status=task.production_run.status if task.production_run else None,
        revision_number=task.revision_number,
        task_id=task.id,
        task_name=task.name,
        template_id=template.id,
        template_name=template.name,
        template_version=template.version,
        render_plan_id=output.render_plan_id,
        creative_goal=output.render_plan.plan_json.get("creative_goal", {}),
        production_contract=output.render_plan.plan_json.get("production_contract", {}),
        render_plan=output.render_plan.plan_json,
        file_path=output.file_path,
        duration_seconds=output.duration_seconds,
        file_size_bytes=output.file_size_bytes,
        status=output.status,
        review_status=output.review_status,
        review_notes=output.review_notes,
        review_feedback=normalized_review_feedback(output.review_feedback_json),
        reviewed_at=output.reviewed_at,
        created_at=output.created_at,
    )


def normalized_review_feedback(feedback: Optional[dict]) -> Optional[dict]:
    if feedback is None:
        return None
    normalized = dict(feedback)
    if "change_requests" not in normalized:
        change_request = normalized.get("change_request")
        if change_request:
            normalized["change_requests"] = [
                {
                    "category": "other",
                    "request": change_request,
                    "target": None,
                    "priority": normalized.get("priority"),
                }
            ]
        else:
            normalized["change_requests"] = []
    return normalized


def output_review_payload_by_id(db: Session, output_id: int) -> OutputReviewRead:
    output = db.get(OutputVideo, output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Output video not found")
    return output_review_payload(output)
