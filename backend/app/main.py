from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse

from app.api.routes import router as api_router
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import GenerationTask, OutputVideo, ProductionRun, RenderPlan, TaskEvent, Template
from app.schemas import HealthResponse
from app.services.auth import token_from_request, user_for_token
from app.services.storage import ensure_storage_dirs
from app.services.system_music import seed_generated_system_music
from app.services.task_queue import task_queue
from app.template_library import BUILTIN_TEMPLATES


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_storage_dirs()
    init_db()
    seed_builtin_template()
    seed_system_music()
    migrate_legacy_production_runs()
    task_queue.start()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.middleware("http")
async def enforce_trial_auth(request, call_next):
    if not settings.require_auth:
        return await call_next(request)
    if not request.url.path.startswith("/api"):
        return await call_next(request)
    if request.url.path in {"/api/auth/register", "/api/auth/login"}:
        return await call_next(request)

    token = token_from_request(request)
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    with SessionLocal() as db:
        user = user_for_token(db, token)
        if user is None:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})
    return await call_next(request)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
    )


def seed_builtin_template() -> None:
    with SessionLocal() as db:
        delete_orphan_task_artifacts(db)
        for legacy_template in db.query(Template):
            if (legacy_template.json_spec or {}).get("type") not in {
                "variant_recipe",
                "video_modification_template",
            }:
                delete_tasks_for_template(db, legacy_template.id)
                db.delete(legacy_template)
        db.flush()

        production_names = {template["name"] for template in BUILTIN_TEMPLATES}
        for stale_template in db.query(Template).filter(Template.is_builtin.is_(True)):
            if stale_template.name not in production_names:
                delete_tasks_for_template(db, stale_template.id)
                db.delete(stale_template)

        for template in BUILTIN_TEMPLATES:
            existing = db.query(Template).filter(Template.name == template["name"]).first()
            if existing is None:
                db.add(
                    Template(
                        name=template["name"],
                        description=template["description"],
                        version=1,
                        json_spec=template["json_spec"],
                        is_builtin=True,
                    )
                )
                continue
            if existing.is_builtin:
                existing.description = template["description"]
                existing.version = max(existing.version, 1)
                existing.json_spec = template["json_spec"]
        db.commit()


def delete_orphan_task_artifacts(db) -> None:
    live_task_ids = db.query(GenerationTask.id)
    db.query(OutputVideo).filter(~OutputVideo.task_id.in_(live_task_ids)).delete(
        synchronize_session=False
    )
    db.query(RenderPlan).filter(~RenderPlan.task_id.in_(live_task_ids)).delete(
        synchronize_session=False
    )
    db.query(TaskEvent).filter(~TaskEvent.task_id.in_(live_task_ids)).delete(
        synchronize_session=False
    )


def delete_tasks_for_template(db, template_id: int) -> None:
    task_ids = [
        task_id
        for (task_id,) in db.query(GenerationTask.id).filter(
            GenerationTask.template_id == template_id
        )
    ]
    if not task_ids:
        return
    db.query(OutputVideo).filter(OutputVideo.task_id.in_(task_ids)).delete(
        synchronize_session=False
    )
    db.query(RenderPlan).filter(RenderPlan.task_id.in_(task_ids)).delete(
        synchronize_session=False
    )
    db.query(TaskEvent).filter(TaskEvent.task_id.in_(task_ids)).delete(
        synchronize_session=False
    )
    db.query(GenerationTask).filter(GenerationTask.id.in_(task_ids)).delete(
        synchronize_session=False
    )


def seed_system_music() -> None:
    with SessionLocal() as db:
        seed_generated_system_music(db)


def migrate_legacy_production_runs() -> None:
    with SessionLocal() as db:
        tasks = (
            db.query(GenerationTask)
            .filter(GenerationTask.production_run_id.is_(None))
            .order_by(GenerationTask.created_at.asc(), GenerationTask.id.asc())
            .all()
        )
        runs_by_key: dict[tuple[int, str, str], ProductionRun] = {}
        for task in tasks:
            prefix = legacy_task_prefix(task)
            minute = task.created_at.strftime("%Y-%m-%d %H:%M")
            key = (task.asset_id, prefix, minute)
            production_run = runs_by_key.get(key)
            if production_run is None:
                production_run = ProductionRun(
                    asset_id=task.asset_id,
                    name=f"{minute} {task.asset.original_filename} - {prefix}",
                    name_prefix=prefix,
                )
                db.add(production_run)
                db.flush()
                runs_by_key[key] = production_run
            task.production_run_id = production_run.id
            task.revision_number = task.revision_number or 1
        db.commit()


def legacy_task_prefix(task: GenerationTask) -> str:
    template_suffix = f" - {task.template.name}"
    if task.name.endswith(template_suffix):
        prefix = task.name[: -len(template_suffix)]
    else:
        prefix = task.name
    return " ".join(prefix.split()) or "legacy-run"
