from pathlib import Path

from app.services.ai_asset_factory.providers.base import AIVideoProvider


class RunwayProvider(AIVideoProvider):
    """Runway API placeholder for the post-MVP generation loop."""

    async def image_to_video(
        self,
        image_path: Path,
        prompt: str,
        duration: int = 4,
    ) -> Path:
        raise NotImplementedError("Runway generation is not wired in the AICF MVP.")
