#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.models import AIAsset, AIAssetKind, AIAssetStatus, AIAssetTag, AIAssetType
from app.services.ffmpeg import FFmpegError, probe_media
from app.services.storage import ai_asset_upload_path, ensure_storage_dirs


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS


@dataclass
class ImportResult:
    source_path: str
    action: str
    target_id: Optional[int] = None
    asset_kind: Optional[str] = None
    asset_type: Optional[str] = None
    status: str = "ok"
    message: Optional[str] = None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch import local images and video clips into Flashcutter ai_assets."
    )
    parser.add_argument("source", type=Path, help="File or directory to import.")
    parser.add_argument(
        "--image-type",
        default=AIAssetType.FRAME.value,
        choices=[item.value for item in AIAssetType],
        help="AI asset type to assign to image files.",
    )
    parser.add_argument(
        "--video-type",
        default=AIAssetType.BROLL.value,
        choices=[item.value for item in AIAssetType],
        help="AI asset type to assign to video files.",
    )
    parser.add_argument(
        "--scope",
        default="system",
        choices=["system", "private"],
        help="Visibility scope. System assets are visible to all users.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Required when --scope private; ignored for system assets.",
    )
    parser.add_argument("--provider", default="media_pack")
    parser.add_argument(
        "--tags",
        default="ads-pack, rights-licensed",
        help="Comma-separated tags added to every imported asset.",
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recursively scan directories.",
    )
    parser.add_argument(
        "--dedupe",
        choices=["sha256", "filename", "off"],
        default="sha256",
        help="Skip files that already appear to be imported.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    if args.scope == "private" and args.user_id is None:
        raise SystemExit("--user-id is required when --scope private")

    source = args.source.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")

    files = discover_files(source, recursive=args.recursive)
    if not files:
        raise SystemExit("No importable files found.")

    if args.dry_run:
        results = [
            ImportResult(
                source_path=str(path),
                action="would_import",
                asset_kind=asset_kind(path),
                asset_type=asset_type_for_path(path, args.image_type, args.video_type),
                status="dry_run",
            )
            for path in files
        ]
    else:
        init_db()
        ensure_storage_dirs()
        with SessionLocal() as db:
            importer = AIAssetImporter(
                db=db,
                scope=args.scope,
                user_id=None if args.scope == "system" else args.user_id,
                image_type=args.image_type,
                video_type=args.video_type,
                provider=args.provider,
                tags=parse_tags(args.tags),
                dedupe=args.dedupe,
            )
            results = [importer.import_path(path) for path in files]

    print_summary(results)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"report: {args.report}")


class AIAssetImporter:
    def __init__(
        self,
        *,
        db: Session,
        scope: str,
        user_id: Optional[int],
        image_type: str,
        video_type: str,
        provider: str,
        tags: list[str],
        dedupe: str,
    ) -> None:
        self.db = db
        self.scope = scope
        self.user_id = user_id
        self.image_type = image_type
        self.video_type = video_type
        self.provider = provider
        self.tags = tags
        self.dedupe = dedupe
        self._hashes: Optional[dict[str, AIAsset]] = None

    def import_path(self, path: Path) -> ImportResult:
        try:
            duplicate = self.find_duplicate(path)
            if duplicate is not None:
                return ImportResult(
                    source_path=str(path),
                    action="skipped_duplicate",
                    target_id=duplicate.id,
                    asset_kind=duplicate.asset_kind,
                    asset_type=duplicate.asset_type,
                    status=duplicate.status,
                    message=f"Already imported as ai_asset #{duplicate.id}",
                )

            kind = asset_kind(path)
            assigned_type = asset_type_for_path(path, self.image_type, self.video_type)
            record = AIAsset(
                user_id=self.user_id,
                scope=self.scope,
                provider=self.provider,
                asset_kind=kind,
                asset_type=assigned_type,
                title=path.stem[:255],
                prompt="Imported from local rights-cleared media pack.",
                original_filename=path.name[:255],
                stored_filename="",
                file_path="",
                mime_type=mimetypes.guess_type(path.name)[0],
                file_size_bytes=path.stat().st_size,
                status=AIAssetStatus.IMPORTING.value,
            )
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)

            destination = ai_asset_upload_path(record.id, path.name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)

            record.stored_filename = destination.name
            record.file_path = str(destination)
            if kind == AIAssetKind.VIDEO.value:
                try:
                    metadata = probe_media(destination)
                    record.duration_seconds = metadata.get("duration_seconds")
                    record.width = metadata.get("width")
                    record.height = metadata.get("height")
                    record.fps = metadata.get("fps")
                    record.status = AIAssetStatus.READY.value
                except FFmpegError as exc:
                    record.status = AIAssetStatus.FAILED.value
                    record.error_message = str(exc)
            else:
                record.status = AIAssetStatus.READY.value

            self.set_tags(record)
            self.db.commit()
            self.db.refresh(record)

            if self._hashes is not None:
                self._hashes[file_sha256(destination)] = record

            return ImportResult(
                source_path=str(path),
                action="imported",
                target_id=record.id,
                asset_kind=record.asset_kind,
                asset_type=record.asset_type,
                status=record.status,
                message=record.error_message,
            )
        except Exception as exc:  # noqa: BLE001 - keep batch imports moving.
            self.db.rollback()
            return ImportResult(
                source_path=str(path),
                action="failed",
                status="failed",
                message=str(exc),
            )

    def find_duplicate(self, path: Path) -> Optional[AIAsset]:
        if self.dedupe == "off":
            return None
        if self.dedupe == "filename":
            return self.db.scalar(
                select(AIAsset)
                .where(AIAsset.original_filename == path.name, AIAsset.scope == self.scope)
                .limit(1)
            )
        if self._hashes is None:
            self._hashes = {}
            for asset in self.db.scalars(select(AIAsset)):
                asset_path = Path(asset.file_path)
                if asset_path.exists() and asset_path.is_file():
                    self._hashes[file_sha256(asset_path)] = asset
        return self._hashes.get(file_sha256(path))

    def set_tags(self, asset: AIAsset) -> None:
        for existing in list(asset.tags):
            self.db.delete(existing)
        values = [asset.asset_type, *self.tags]
        seen = set()
        for value in values:
            tag = value.strip().lower()
            if not tag or tag in seen:
                continue
            seen.add(tag)
            asset.tags.append(AIAssetTag(tag=tag[:64]))


def discover_files(source: Path, *, recursive: bool) -> list[Path]:
    if source.is_file():
        files = [source]
    else:
        pattern = "**/*" if recursive else "*"
        files = [path for path in source.glob(pattern) if path.is_file()]
    return sorted(path.resolve() for path in files if path.suffix.lower() in DEFAULT_EXTENSIONS)


def asset_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return AIAssetKind.IMAGE.value
    if suffix in VIDEO_EXTENSIONS:
        return AIAssetKind.VIDEO.value
    raise ValueError(f"Unsupported media file: {path}")


def asset_type_for_path(path: Path, image_type: str, video_type: str) -> str:
    return image_type if asset_kind(path) == AIAssetKind.IMAGE.value else video_type


def parse_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.replace("，", ",").split(",") if tag.strip()]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def print_summary(results: Iterable[ImportResult]) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.action] = counts.get(result.action, 0) + 1
        target = f" ai_asset#{result.target_id}" if result.target_id else ""
        kind = f" {result.asset_kind}/{result.asset_type}" if result.asset_kind else ""
        message = f" - {result.message}" if result.message else ""
        print(f"{result.action}: {result.source_path}{target}{kind} [{result.status}]{message}")
    print("summary:", ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))


if __name__ == "__main__":
    main()
