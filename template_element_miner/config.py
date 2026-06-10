from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov"}

ASSET_CATEGORIES = [
    "frame",
    "product_frame",
    "phone_frame",
    "photo_frame",
    "sticker",
    "discount_badge",
    "arrow",
    "speech_bubble",
    "cta_button",
    "price_bar",
    "title_bar",
    "product_card",
    "layout_block",
    "unknown",
]


@dataclass(frozen=True)
class MinerPaths:
    input_dir: Path = Path("data/template_element_miner/input")
    output_dir: Path = Path("data/template_element_miner/output")
    assets_dir: Path = Path("data/template_element_miner/assets")

    @property
    def frames_dir(self) -> Path:
        return self.output_dir / "frames"

    @property
    def candidates_dir(self) -> Path:
        return self.output_dir / "candidates"

    @property
    def debug_dir(self) -> Path:
        return self.output_dir / "debug"

    @property
    def clusters_dir(self) -> Path:
        return self.output_dir / "clusters"

    @property
    def review_dir(self) -> Path:
        return self.output_dir / "review"


@dataclass(frozen=True)
class DetectionConfig:
    min_width_px: int = 32
    min_height_px: int = 24
    min_area_ratio: float = 0.002
    max_area_ratio: float = 0.72
    max_thin_aspect: float = 12.0
    min_crop_stddev: float = 10.0
    min_blur_laplacian_var: float = 12.0
    merge_iou_threshold: float = 0.72
    contour_min_rectangularity: float = 0.45
    bottom_bar_min_height_ratio: float = 0.06
    bottom_bar_max_height_ratio: float = 0.24


@dataclass(frozen=True)
class ClusterConfig:
    duplicate_phash_distance: int = 4
    cluster_phash_distance: int = 12
    aspect_ratio_tolerance: float = 0.35
    area_ratio_tolerance: float = 0.12
    dominant_color_distance: float = 95.0
    contact_sheet_thumb_size: tuple[int, int] = (160, 120)
    contact_sheet_columns: int = 5


@dataclass(frozen=True)
class MinerConfig:
    paths: MinerPaths = field(default_factory=MinerPaths)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    cluster: ClusterConfig = field(default_factory=ClusterConfig)
    default_fps: float = 1.0
