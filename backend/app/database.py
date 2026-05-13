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


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
