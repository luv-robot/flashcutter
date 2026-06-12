from functools import lru_cache
import os
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "flashcutter"
    environment: str = "development"
    database_url: str = "sqlite:///./flashcutter.db"
    storage_root: Path = Field(default=Path("storage"))
    default_template_name: str = "prod_pain_demo_cta_vertical"
    require_auth: bool = False
    allow_registration: bool = True
    ai_clone_provider: str = "mock"
    comfyui_base_url: str = ""
    comfyui_api_key: str = ""
    comfyui_timeout_seconds: float = 30.0
    comfyui_poll_interval_seconds: float = 5.0
    comfyui_max_wait_seconds: float = 900.0
    ai_clone_image_workflow_path: str = ""
    ai_clone_video_workflow_path: str = ""
    copy_ai_provider: str = "rule_based"
    copy_ai_base_url: str = ""
    copy_ai_api_key: str = ""
    copy_ai_model: str = ""
    copy_ai_timeout_seconds: float = 12.0
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("FLASHCUTTER_APP_NAME", "flashcutter"),
        environment=os.getenv("FLASHCUTTER_ENVIRONMENT", "development"),
        database_url=os.getenv("FLASHCUTTER_DATABASE_URL", "sqlite:///./flashcutter.db"),
        storage_root=Path(os.getenv("FLASHCUTTER_STORAGE_ROOT", "storage")),
        default_template_name=os.getenv(
            "FLASHCUTTER_DEFAULT_TEMPLATE_NAME", "prod_pain_demo_cta_vertical"
        ),
        require_auth=parse_bool_env(os.getenv("FLASHCUTTER_REQUIRE_AUTH", "false")),
        allow_registration=parse_bool_env(
            os.getenv("FLASHCUTTER_ALLOW_REGISTRATION", "true")
        ),
        ai_clone_provider=os.getenv("FLASHCUTTER_AI_CLONE_PROVIDER", "mock").strip().lower(),
        comfyui_base_url=os.getenv("FLASHCUTTER_COMFYUI_BASE_URL", "").strip().rstrip("/"),
        comfyui_api_key=os.getenv("FLASHCUTTER_COMFYUI_API_KEY", "").strip(),
        comfyui_timeout_seconds=parse_float_env(
            os.getenv("FLASHCUTTER_COMFYUI_TIMEOUT_SECONDS", "30"), 30.0
        ),
        comfyui_poll_interval_seconds=parse_float_env(
            os.getenv("FLASHCUTTER_COMFYUI_POLL_INTERVAL_SECONDS", "5"), 5.0
        ),
        comfyui_max_wait_seconds=parse_float_env(
            os.getenv("FLASHCUTTER_COMFYUI_MAX_WAIT_SECONDS", "900"), 900.0
        ),
        ai_clone_image_workflow_path=os.getenv(
            "FLASHCUTTER_AI_CLONE_IMAGE_WORKFLOW_PATH", ""
        ).strip(),
        ai_clone_video_workflow_path=os.getenv(
            "FLASHCUTTER_AI_CLONE_VIDEO_WORKFLOW_PATH", ""
        ).strip(),
        copy_ai_provider=os.getenv("FLASHCUTTER_COPY_AI_PROVIDER", "rule_based")
        .strip()
        .lower(),
        copy_ai_base_url=os.getenv("FLASHCUTTER_COPY_AI_BASE_URL", "")
        .strip()
        .rstrip("/"),
        copy_ai_api_key=os.getenv("FLASHCUTTER_COPY_AI_API_KEY", "").strip(),
        copy_ai_model=os.getenv("FLASHCUTTER_COPY_AI_MODEL", "").strip(),
        copy_ai_timeout_seconds=parse_float_env(
            os.getenv("FLASHCUTTER_COPY_AI_TIMEOUT_SECONDS", "12"), 12.0
        ),
        cors_origins=parse_csv_env(
            os.getenv(
                "FLASHCUTTER_CORS_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173",
            )
        ),
    )


def parse_csv_env(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_bool_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_float_env(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
