from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "flashcutter"
    environment: str = "development"
    database_url: str = "sqlite:///./flashcutter.db"
    storage_root: Path = Field(default=Path("storage"))
    default_template_name: str = "simple_concat"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("FLASHCUTTER_APP_NAME", "flashcutter"),
        environment=os.getenv("FLASHCUTTER_ENVIRONMENT", "development"),
        database_url=os.getenv("FLASHCUTTER_DATABASE_URL", "sqlite:///./flashcutter.db"),
        storage_root=Path(os.getenv("FLASHCUTTER_STORAGE_ROOT", "storage")),
        default_template_name=os.getenv(
            "FLASHCUTTER_DEFAULT_TEMPLATE_NAME", "simple_concat"
        ),
    )
