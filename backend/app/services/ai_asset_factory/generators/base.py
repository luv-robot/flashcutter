from abc import ABC, abstractmethod
from pathlib import Path


class AIClipGenerator(ABC):
    """Interface for producing reusable AI clips from source images."""

    @abstractmethod
    async def generate_clip(
        self,
        image_path: Path,
        prompt: str,
        duration: int,
        output_path: Path,
    ) -> Path:
        raise NotImplementedError
