from abc import ABC, abstractmethod
from pathlib import Path


class AIVideoProvider(ABC):
    """Interface for provider-backed image-to-video generation."""

    @abstractmethod
    async def image_to_video(
        self,
        image_path: Path,
        prompt: str,
        duration: int = 4,
    ) -> Path:
        raise NotImplementedError
