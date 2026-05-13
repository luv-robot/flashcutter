from pathlib import Path
from typing import List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import (
    Asset,
    AssetStatus,
    GenerationTask,
    OutputVideo,
    OutputVideoStatus,
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
    AssetRead,
    AssetImportUrl,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthResponse,
    AuthUserRead,
    GenerationTaskBatchCreate,
    GenerationTaskCreate,
    GenerationTaskRead,
    OutputVideoRead,
    OutputReviewRead,
    OutputReviewUpdate,
    RenderVariantsRequest,
    RenderPlanRead,
    SegmentRead,
    TaskRunRequest,
    TaskRunResponse,
    TaskEventRead,
    TemplateCoverRegion,
    TemplateCreate,
    TemplateRead,
    TemplateSpec,
    TemplateTextOverlay,
    TemplateUpdate,
    TemplateValidationRead,
    TemplateValidationRequest,
    TextRegionDetectionRead,
    VariantPreflightItem,
    VariantPreflightRead,
)
from app.services.ffmpeg import (
    FFmpegError,
    probe_media,
    render_card_clip,
    render_concat,
    render_timeline,
    split_fixed_segments,
)
from app.services.auth import (
    create_session,
    ensure_unique_phone,
    hash_password,
    normalize_phone,
    verify_password,
)
from app.services.storage import (
    asset_segments_dir,
    asset_analysis_dir,
    asset_upload_path,
    concat_list_path,
    filename_from_url,
    save_upload_file,
    task_card_path,
    task_output_path,
)
from app.services.task_queue import task_queue
from app.services.text_detection import detect_text_regions

router = APIRouter(prefix="/api")


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
        request = Request(payload.url, headers={"User-Agent": "flashcutter-mvp/0.1"})
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
        json_spec=payload.json_spec.model_dump(exclude_none=True),
        is_builtin=payload.is_builtin,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.post("/templates/validate", response_model=TemplateValidationRead)
def validate_template(payload: TemplateValidationRequest) -> TemplateValidationRead:
    normalized = normalize_template_spec(payload.json_spec)
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
        template.json_spec = payload.json_spec.model_dump(exclude_none=True)
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
    payload: GenerationTaskCreate, db: Session = Depends(get_db)
) -> GenerationTaskRead:
    asset = db.get(Asset, payload.asset_id)
    template = db.get(Template, payload.template_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    task = GenerationTask(
        name=payload.name,
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
    payload: GenerationTaskBatchCreate, db: Session = Depends(get_db)
) -> List[GenerationTaskRead]:
    return create_tasks_for_asset_templates(
        db=db,
        asset_id=payload.asset_id,
        template_ids=payload.template_ids,
        name_prefix=payload.name_prefix,
        params_json=payload.params_json,
    )


def create_tasks_for_asset_templates(
    db: Session,
    asset_id: int,
    template_ids: List[int],
    name_prefix: str,
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

    tasks = []
    for template in templates:
        task = GenerationTask(
            name=f"{name_prefix} - {template.name}",
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


@router.post("/assets/{asset_id}/render-variants", response_model=List[OutputReviewRead])
def render_asset_variants(
    asset_id: int, payload: RenderVariantsRequest, db: Session = Depends(get_db)
) -> List[OutputReviewRead]:
    tasks = create_tasks_for_asset_templates(
        db=db,
        asset_id=asset_id,
        template_ids=payload.template_ids,
        name_prefix=payload.name_prefix,
        params_json=payload.params_json,
    )
    outputs = []
    for task in tasks:
        task_result = run_task_pipeline(task.id, payload=None, db=db)
        outputs.append(output_review_payload_by_id(db, task_result.output.id))
    return outputs


@router.post("/assets/{asset_id}/render-variants/enqueue", response_model=List[GenerationTaskRead])
def enqueue_asset_variants(
    asset_id: int, payload: RenderVariantsRequest, db: Session = Depends(get_db)
) -> List[GenerationTaskRead]:
    tasks = create_tasks_for_asset_templates(
        db=db,
        asset_id=asset_id,
        template_ids=payload.template_ids,
        name_prefix=payload.name_prefix,
        params_json=payload.params_json,
    )
    for task in tasks:
        mark_task_progress(
            db=db,
            task=task,
            status=TaskStatus.WAITING.value,
            progress_percent=0,
            progress_message="Waiting in render queue",
        )
        task_queue.enqueue(task.id, run_queued_task_pipeline)
    return tasks


@router.post("/assets/{asset_id}/render-variants/preflight", response_model=VariantPreflightRead)
def preflight_asset_variants(
    asset_id: int, payload: RenderVariantsRequest, db: Session = Depends(get_db)
) -> VariantPreflightRead:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    templates = list(db.scalars(select(Template).where(Template.id.in_(payload.template_ids))))
    found_ids = {template.id for template in templates}
    missing_ids = [template_id for template_id in payload.template_ids if template_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Templates not found: {missing_ids}")

    ordered_templates = sorted(templates, key=lambda template: payload.template_ids.index(template.id))
    items = []
    for template in ordered_templates:
        task = GenerationTask(
            name="preflight",
            asset_id=asset.id,
            template_id=template.id,
            template=template,
            params_json=payload.params_json or {},
        )
        spec = template_spec_for_task(task)
        warnings = template_warnings(spec)
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
                warnings=warnings,
            )
        )

    return VariantPreflightRead(
        asset_id=asset.id,
        asset_filename=asset.original_filename,
        asset_duration_seconds=asset.duration_seconds,
        items=items,
    )


@router.get("/tasks", response_model=List[GenerationTaskRead])
def list_tasks(db: Session = Depends(get_db)) -> List[GenerationTaskRead]:
    return list(db.scalars(select(GenerationTask).order_by(GenerationTask.created_at.desc())))


@router.get("/tasks/{task_id}/events", response_model=List[TaskEventRead])
def list_task_events(task_id: int, db: Session = Depends(get_db)) -> List[TaskEventRead]:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return list(
        db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .order_by(TaskEvent.created_at)
        )
    )


@router.post("/tasks/{task_id}/render-plan", response_model=RenderPlanRead)
def build_render_plan(task_id: int, db: Session = Depends(get_db)) -> RenderPlanRead:
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
        "clips": [
            {
                "segment_id": segment.id,
                "source_path": segment.file_path,
                "start_time": segment.start_time,
                "duration_seconds": segment.duration_seconds,
            }
            for segment in selected_segments
        ],
        "output": {
            "path": str(task_output_path(task.id)),
            "format": template_spec.output.format,
            "width": template_spec.output.width,
            "height": template_spec.output.height,
            "fps": template_spec.output.fps,
        },
        "layout": {
            "fit": template_spec.layout.fit,
            "safe_area_top": template_spec.layout.safe_area_top,
            "safe_area_bottom": template_spec.layout.safe_area_bottom,
        },
        "selection": template_spec.selection.model_dump(exclude_none=True),
        "transformations": template_spec.transformations.model_dump(exclude_none=True),
        "intro_card": template_spec.intro_card.model_dump() if template_spec.intro_card else None,
        "outro_card": template_spec.outro_card.model_dump() if template_spec.outro_card else None,
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


@router.post("/tasks/{task_id}/render", response_model=OutputVideoRead)
def render_task(task_id: int, db: Session = Depends(get_db)) -> OutputVideoRead:
    return render_task_output(db=db, task_id=task_id)


@router.post("/tasks/{task_id}/enqueue", response_model=GenerationTaskRead)
def enqueue_task(task_id: int, db: Session = Depends(get_db)) -> GenerationTaskRead:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    mark_task_progress(
        db=db,
        task=task,
        status=TaskStatus.WAITING.value,
        progress_percent=0,
        progress_message="Waiting in render queue",
    )
    task_queue.enqueue(task.id, run_queued_task_pipeline)
    db.refresh(task)
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
    intro_card_spec = task.render_plan.plan_json.get("intro_card")
    outro_card_spec = task.render_plan.plan_json.get("outro_card")
    output_path = task_output_path(task.id)
    has_intro = bool(intro_card_spec and intro_card_spec.get("enabled"))
    has_outro = bool(outro_card_spec and outro_card_spec.get("enabled"))
    has_cards = has_intro or has_outro
    try:
        if has_cards:
            width = output_spec.get("width")
            height = output_spec.get("height")
            fps = output_spec.get("fps")
            if not (width and height and fps):
                raise FFmpegError(
                    "Intro/outro cards require delivery.width, height, and fps to be set"
                )
            if has_intro:
                intro_path = task_card_path(task.id, "intro")
                render_card_clip(
                    output_path=intro_path,
                    duration_seconds=intro_card_spec["duration_seconds"],
                    width=width,
                    height=height,
                    fps=float(fps),
                    text=intro_card_spec["text"],
                    subtitle=intro_card_spec.get("subtitle"),
                    background_color=intro_card_spec.get("background_color", "black"),
                    font_color=intro_card_spec.get("font_color", "white"),
                    font_size=int(intro_card_spec.get("font_size", 72)),
                    subtitle_font_color=intro_card_spec.get("subtitle_font_color", "white"),
                    subtitle_font_size=int(intro_card_spec.get("subtitle_font_size", 40)),
                )
                segment_paths = [intro_path] + segment_paths
            if has_outro:
                outro_path = task_card_path(task.id, "outro")
                render_card_clip(
                    output_path=outro_path,
                    duration_seconds=outro_card_spec["duration_seconds"],
                    width=width,
                    height=height,
                    fps=float(fps),
                    text=outro_card_spec["text"],
                    subtitle=outro_card_spec.get("subtitle"),
                    background_color=outro_card_spec.get("background_color", "black"),
                    font_color=outro_card_spec.get("font_color", "white"),
                    font_size=int(outro_card_spec.get("font_size", 72)),
                    subtitle_font_color=outro_card_spec.get("subtitle_font_color", "white"),
                    subtitle_font_size=int(outro_card_spec.get("subtitle_font_size", 40)),
                )
                segment_paths = segment_paths + [outro_path]

        if has_cards or should_render_with_filters(
            output_spec, layout_spec, transformations_spec
        ):
            render_kwargs = {
                "segment_paths": segment_paths,
                "concat_file": concat_list_path(task.id),
                "output_path": output_path,
                "width": output_spec.get("width"),
                "height": output_spec.get("height"),
                "fps": output_spec.get("fps"),
                "fit": layout_spec.get("fit", "original"),
                "safe_area_top": int(layout_spec.get("safe_area_top") or 0),
                "safe_area_bottom": int(layout_spec.get("safe_area_bottom") or 0),
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
        or layout_spec.get("safe_area_top")
        or layout_spec.get("safe_area_bottom")
        or has_transformations(transformations_spec)
    )


def has_transformations(transformations_spec: Optional[dict] = None) -> bool:
    for value in (transformations_spec or {}).values():
        if value is None or value is False:
            continue
        if isinstance(value, (list, dict, str)) and not value:
            continue
        return True
    return False


@router.post("/tasks/{task_id}/run", response_model=TaskRunResponse)
def run_task_pipeline(
    task_id: int,
    payload: Optional[TaskRunRequest] = None,
    db: Session = Depends(get_db),
) -> TaskRunResponse:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

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
            run_task_pipeline(task_id=task_id, payload=None, db=db)
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


def template_spec_for_task(task: GenerationTask) -> TemplateSpec:
    spec = normalize_template_spec(TemplateSpec.model_validate(task.template.json_spec or {}))
    params = task.params_json or {}

    output_params = params.get("output")
    if isinstance(output_params, dict):
        output = spec.output.model_copy(update=output_params)
        spec = spec.model_copy(update={"output": output})

    selection_params = params.get("selection")
    if isinstance(selection_params, dict):
        selection = spec.selection.model_copy(update=selection_params)
        spec = spec.model_copy(update={"selection": selection})

    segments_params = params.get("segments")
    if isinstance(segments_params, dict):
        segments = spec.segments.model_copy(update=segments_params)
        spec = spec.model_copy(update={"segments": segments})

    layout_params = params.get("layout")
    if isinstance(layout_params, dict):
        layout = spec.layout.model_copy(update=layout_params)
        spec = spec.model_copy(update={"layout": layout})

    transformations_params = params.get("transformations")
    if isinstance(transformations_params, dict):
        transformations = spec.transformations.model_copy(update=transformations_params)
        spec = spec.model_copy(update={"transformations": transformations})

    return normalize_template_spec(spec)


def normalize_template_spec(spec: TemplateSpec) -> TemplateSpec:
    if spec.editing is not None:
        spec = spec.model_copy(
            update={
                "segments": spec.segments.model_copy(
                    update={"segment_seconds": spec.editing.clip_duration_seconds}
                ),
                "selection": spec.selection.model_copy(
                    update={
                        "mode": "first_n"
                        if spec.editing.max_clip_count is not None
                        else spec.selection.mode,
                        "count": spec.editing.max_clip_count,
                        "max_total_duration": spec.editing.target_duration_seconds,
                    }
                ),
            }
        )

    bar = spec.subtitle_bar
    delivery = spec.delivery

    # Auto-reserve safe area to match an enabled subtitle bar so the source
    # video is not hidden under it. Operator-supplied values always win.
    if bar is not None and bar.enabled and delivery is not None:
        update_delivery = {}
        if bar.position == "top" and delivery.safe_area_top == 0:
            update_delivery["safe_area_top"] = bar.bar_height
        if bar.position == "bottom" and delivery.safe_area_bottom == 0:
            update_delivery["safe_area_bottom"] = bar.bar_height
        if update_delivery:
            delivery = delivery.model_copy(update=update_delivery)
            spec = spec.model_copy(update={"delivery": delivery})

    if delivery is not None:
        spec = spec.model_copy(
            update={
                "output": spec.output.model_copy(
                    update={
                        "width": delivery.width,
                        "height": delivery.height,
                        "fps": delivery.fps,
                        "format": delivery.format,
                    }
                ),
                "layout": spec.layout.model_copy(
                    update={
                        "fit": delivery.fit,
                        "safe_area_top": delivery.safe_area_top,
                        "safe_area_bottom": delivery.safe_area_bottom,
                    }
                ),
            }
        )

    # Translate subtitle_bar into the existing cover_regions + text_overlays
    # machinery so the renderer does not need to know about a new field.
    if bar is not None and bar.enabled:
        width = spec.output.width
        height = spec.output.height
        if width and height:
            bar_y = _subtitle_bar_y(bar.position, bar.bar_height, height)
            cover_regions = list(spec.transformations.cover_regions)
            text_overlays = list(spec.transformations.text_overlays)
            if bar.bar_color and bar.bar_color.lower() != "none":
                cover_regions.append(
                    TemplateCoverRegion.model_validate(
                        {
                            "x": 0,
                            "y": bar_y,
                            "width": width,
                            "height": bar.bar_height,
                            "color": bar.bar_color,
                        }
                    )
                )
            text_overlays.append(
                TemplateTextOverlay.model_validate(
                    {
                        "text": bar.text,
                        "x": "(w-text_w)/2",
                        "y": f"{bar_y}+({bar.bar_height}-text_h)/2",
                        "font_size": bar.font_size,
                        "font_color": bar.font_color,
                        "box_color": None,
                        "box_padding": 0,
                    }
                )
            )
            spec = spec.model_copy(
                update={
                    "transformations": spec.transformations.model_copy(
                        update={
                            "cover_regions": cover_regions,
                            "text_overlays": text_overlays,
                        }
                    )
                }
            )

    return spec


def _subtitle_bar_y(position: str, bar_height: int, frame_height: int) -> int:
    if position == "top":
        return 0
    if position == "center":
        return max(0, (frame_height - bar_height) // 2)
    return max(0, frame_height - bar_height)


def validate_render_spec(spec: TemplateSpec) -> None:
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
    has_cards = (spec.intro_card and spec.intro_card.enabled) or (
        spec.outro_card and spec.outro_card.enabled
    )
    if has_cards and not (spec.output.width and spec.output.height and spec.output.fps):
        raise HTTPException(
            status_code=400,
            detail="Intro/outro cards require delivery.width, height, and fps to be set",
        )
    if spec.output.height is not None and (
        spec.layout.safe_area_top + spec.layout.safe_area_bottom
    ) >= spec.output.height:
        raise HTTPException(
            status_code=400,
            detail="safe_area_top + safe_area_bottom must leave room for content",
        )


def template_warnings(spec: TemplateSpec) -> List[str]:
    warnings = []
    if spec.delivery and spec.delivery.aspect_ratio != "source":
        if not spec.delivery.width or not spec.delivery.height:
            warnings.append("delivery.aspect_ratio is set but width/height are missing.")
    if spec.layout.fit in {"cover", "contain"} and (
        not spec.output.width or not spec.output.height
    ):
        warnings.append("cover/contain fit modes need output width and height.")
    if spec.selection.mode == "first_n" and not spec.selection.count:
        warnings.append("selection.mode first_n is easier to review with selection.count.")
    if not spec.creative_goal.title:
        warnings.append("creative_goal.title helps reviewers understand the variant.")
    if not spec.review_notes:
        warnings.append("review_notes should describe the operator review focus.")
    target_duration = (
        spec.editing.target_duration_seconds
        if spec.editing and spec.editing.target_duration_seconds
        else None
    )
    card_total = 0.0
    if spec.intro_card and spec.intro_card.enabled:
        card_total += spec.intro_card.duration_seconds
    if spec.outro_card and spec.outro_card.enabled:
        card_total += spec.outro_card.duration_seconds
    if target_duration and card_total > target_duration * 0.5:
        warnings.append(
            "intro/outro cards consume more than half the target duration; consider shortening."
        )
    if spec.subtitle_bar and spec.subtitle_bar.enabled and not spec.output.width:
        warnings.append("subtitle_bar requires delivery.width and height to be set.")
    return warnings


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
    # Concatenating cards + segments often drifts the averaged fps by ~1%.
    # The tolerance only needs to catch order-of-magnitude mistakes (15 vs 30, 30 vs 60).
    if expected_fps and actual_fps and abs(float(actual_fps) - float(expected_fps)) > 1.5:
        raise FFmpegError(f"Rendered fps {actual_fps:.2f} did not match expected {expected_fps}")


def select_segments_for_template(
    segments: List[Segment], template_spec: TemplateSpec
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
def list_outputs(db: Session = Depends(get_db)) -> List[OutputVideoRead]:
    return list(db.scalars(select(OutputVideo).order_by(OutputVideo.created_at.desc())))


@router.get("/outputs/review", response_model=List[OutputReviewRead])
def list_outputs_for_review(db: Session = Depends(get_db)) -> List[OutputReviewRead]:
    outputs = list(db.scalars(select(OutputVideo).order_by(OutputVideo.created_at.desc())))
    return [output_review_payload(output) for output in outputs]


@router.get("/outputs/{output_id}/file")
def get_output_file(output_id: int, db: Session = Depends(get_db)) -> FileResponse:
    output = db.get(OutputVideo, output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Output video not found")
    path = Path(output.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(path, media_type="video/mp4", filename=output.filename)


@router.get("/assets/{asset_id}/outputs", response_model=List[OutputReviewRead])
def list_asset_outputs(asset_id: int, db: Session = Depends(get_db)) -> List[OutputReviewRead]:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    outputs = list(
        db.scalars(
            select(OutputVideo)
            .join(GenerationTask)
            .where(GenerationTask.asset_id == asset_id)
            .order_by(OutputVideo.created_at.desc())
        )
    )
    return [output_review_payload(output) for output in outputs]


@router.patch("/outputs/{output_id}/review", response_model=OutputReviewRead)
def update_output_review(
    output_id: int, payload: OutputReviewUpdate, db: Session = Depends(get_db)
) -> OutputReviewRead:
    output = db.get(OutputVideo, output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Output video not found")

    valid_statuses = {status.value for status in ReviewStatus}
    if payload.review_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid review_status. Expected one of: {sorted(valid_statuses)}",
        )

    output.review_status = payload.review_status
    output.review_notes = payload.review_notes
    output.review_feedback_json = {
        "reviewer_name": payload.reviewer_name,
        "change_request": payload.change_request,
        "priority": payload.priority,
        "tags": payload.tags,
    }
    output.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(output)
    return output_review_payload(output)


def output_review_payload(output: OutputVideo) -> OutputReviewRead:
    task = output.task
    asset = task.asset
    template = task.template
    return OutputReviewRead(
        output_id=output.id,
        asset_id=asset.id,
        asset_filename=asset.original_filename,
        task_id=task.id,
        task_name=task.name,
        template_id=template.id,
        template_name=template.name,
        template_version=template.version,
        render_plan_id=output.render_plan_id,
        file_path=output.file_path,
        duration_seconds=output.duration_seconds,
        file_size_bytes=output.file_size_bytes,
        status=output.status,
        review_status=output.review_status,
        review_notes=output.review_notes,
        review_feedback=output.review_feedback_json,
        reviewed_at=output.reviewed_at,
        created_at=output.created_at,
    )


def output_review_payload_by_id(db: Session, output_id: int) -> OutputReviewRead:
    output = db.get(OutputVideo, output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Output video not found")
    return output_review_payload(output)
