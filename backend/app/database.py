from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_output_review_columns()
    ensure_sqlite_task_progress_columns()
    ensure_sqlite_task_user_column()
    ensure_sqlite_task_production_run_column()
    ensure_sqlite_music_scope_column()
    ensure_sqlite_music_rights_columns()
    ensure_sqlite_ai_asset_columns()
    ensure_sqlite_ai_clone_columns()


def ensure_sqlite_output_review_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "output_videos" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("output_videos")}
    with engine.begin() as connection:
        if "review_status" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE output_videos "
                    "ADD COLUMN review_status VARCHAR(32) DEFAULT 'pending_review'"
                )
            )
        if "review_notes" not in columns:
            connection.execute(text("ALTER TABLE output_videos ADD COLUMN review_notes TEXT"))
        if "reviewed_at" not in columns:
            connection.execute(
                text("ALTER TABLE output_videos ADD COLUMN reviewed_at DATETIME")
            )
        if "review_feedback_json" not in columns:
            connection.execute(
                text("ALTER TABLE output_videos ADD COLUMN review_feedback_json JSON")
            )


def ensure_sqlite_task_progress_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "generation_tasks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("generation_tasks")}
    with engine.begin() as connection:
        if "progress_percent" not in columns:
            connection.execute(
                text("ALTER TABLE generation_tasks ADD COLUMN progress_percent INTEGER DEFAULT 0")
            )
        if "progress_message" not in columns:
            connection.execute(
                text("ALTER TABLE generation_tasks ADD COLUMN progress_message VARCHAR(255)")
            )


def ensure_sqlite_task_user_column() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "generation_tasks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("generation_tasks")}
    with engine.begin() as connection:
        if "user_id" not in columns:
            connection.execute(text("ALTER TABLE generation_tasks ADD COLUMN user_id INTEGER"))


def ensure_sqlite_task_production_run_column() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "generation_tasks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("generation_tasks")}
    with engine.begin() as connection:
        if "production_run_id" not in columns:
            connection.execute(
                text("ALTER TABLE generation_tasks ADD COLUMN production_run_id INTEGER")
            )
        if "revision_number" not in columns:
            connection.execute(
                text("ALTER TABLE generation_tasks ADD COLUMN revision_number INTEGER DEFAULT 1")
            )


def ensure_sqlite_music_scope_column() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "music_tracks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("music_tracks")}
    with engine.begin() as connection:
        if "scope" not in columns:
            connection.execute(
                text("ALTER TABLE music_tracks ADD COLUMN scope VARCHAR(32) DEFAULT 'private'")
            )


def ensure_sqlite_music_rights_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "music_tracks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("music_tracks")}
    column_specs = {
        "artist": "VARCHAR(255)",
        "license_name": "VARCHAR(120)",
        "license_url": "VARCHAR(1024)",
        "source_url": "VARCHAR(1024)",
        "attribution_text": "TEXT",
        "mood": "VARCHAR(120)",
        "bpm": "INTEGER",
    }
    with engine.begin() as connection:
        for name, sql_type in column_specs.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE music_tracks ADD COLUMN {name} {sql_type}"))


def ensure_sqlite_ai_asset_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "ai_assets" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("ai_assets")}
    with engine.begin() as connection:
        if "source_image_path" not in columns:
            connection.execute(
                text("ALTER TABLE ai_assets ADD COLUMN source_image_path VARCHAR(1024)")
            )


def ensure_sqlite_ai_clone_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "ai_clone_jobs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("ai_clone_jobs")}
    column_specs = {
        "simulated_queue_ahead": "INTEGER DEFAULT 0",
    }
    with engine.begin() as connection:
        for name, sql_type in column_specs.items():
            if name not in columns:
                connection.execute(
                    text(f"ALTER TABLE ai_clone_jobs ADD COLUMN {name} {sql_type}")
                )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
