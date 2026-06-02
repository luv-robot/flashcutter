#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
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
from app.models import (
    Asset,
    AssetStatus,
    CreativeReference,
    Segment,
    SegmentStatus,
)
from app.services.ffmpeg import FFmpegError, probe_media, split_fixed_segments
from app.services.storage import asset_segments_dir, asset_upload_path, ensure_storage_dirs


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".webm",
    ".avi",
    ".mkv",
}
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}
DEFAULT_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
PRODUCTION_USAGE = {"production_asset", "asset", "source", "source_video", "video"}
REFERENCE_USAGE = {"reference", "reference_only", "creative_reference", "sample"}


@dataclass
class ImportRow:
    path: Path
    usage_type: str
    title: Optional[str] = None
    rights_status: Optional[str] = None
    industry: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None


@dataclass
class ImportResult:
    source_path: str
    action: str
    target_type: str
    target_id: Optional[int] = None
    status: str = "ok"
    message: Optional[str] = None
    segments: int = 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Batch import rights-cleared videos into Flashcutter assets, or local "
            "ad samples into creative references."
        )
    )
    parser.add_argument(
        "source",
        type=Path,
        help="File or directory to import. Manifest paths are resolved relative to this directory.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=(
            "Optional CSV with columns: filename/path, title, usage_type, rights_status, "
            "industry, tags, notes."
        ),
    )
    parser.add_argument(
        "--kind",
        choices=["production_asset", "reference_only"],
        default="production_asset",
        help="Default import type when manifest rows do not specify usage_type.",
    )
    parser.add_argument(
        "--segment-seconds",
        type=float,
        default=None,
        help="If set for production videos, split imported videos into fixed-length segments.",
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recursively scan directories when no manifest is provided.",
    )
    parser.add_argument(
        "--dedupe",
        choices=["sha256", "filename", "off"],
        default="sha256",
        help="Skip files that already appear to be imported.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without writing files or database rows.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional JSON report path. Defaults to printing a summary only.",
    )
    args = parser.parse_args()

    if args.segment_seconds is not None and args.segment_seconds <= 0:
        raise SystemExit("--segment-seconds must be greater than 0")

    source = args.source.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")

    rows = (
        read_manifest(args.manifest.expanduser().resolve(), source, args.kind)
        if args.manifest
        else discover_rows(source, args.kind, recursive=args.recursive)
    )
    if not rows:
        raise SystemExit("No importable files found.")

    if args.dry_run:
        results = dry_run(rows)
    else:
        init_db()
        ensure_storage_dirs()
        with SessionLocal() as db:
            importer = BatchImporter(
                db=db,
                segment_seconds=args.segment_seconds,
                dedupe=args.dedupe,
            )
            results = [importer.import_row(row) for row in rows]

    print_summary(results)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"report: {args.report}")


class BatchImporter:
    def __init__(
        self,
        *,
        db: Session,
        segment_seconds: Optional[float],
        dedupe: str,
    ) -> None:
        self.db = db
        self.segment_seconds = segment_seconds
        self.dedupe = dedupe
        self._asset_hashes: Optional[dict[str, Asset]] = None

    def import_row(self, row: ImportRow) -> ImportResult:
        try:
            usage_type = normalize_usage_type(row.usage_type)
            if usage_type == "production_asset":
                return self.import_production_asset(row)
            return self.import_creative_reference(row)
        except Exception as exc:  # noqa: BLE001 - batch import should continue per file.
            self.db.rollback()
            return ImportResult(
                source_path=str(row.path),
                action="failed",
                target_type="unknown",
                status="failed",
                message=str(exc),
            )

    def import_production_asset(self, row: ImportRow) -> ImportResult:
        if not is_video_file(row.path):
            return ImportResult(
                source_path=str(row.path),
                action="skipped",
                target_type="asset",
                status="skipped",
                message="Production assets must be video files.",
            )

        duplicate = self.find_duplicate_asset(row.path)
        if duplicate is not None:
            return ImportResult(
                source_path=str(row.path),
                action="skipped_duplicate",
                target_type="asset",
                target_id=duplicate.id,
                status=duplicate.status,
                message=f"Already imported as asset #{duplicate.id}",
                segments=len(duplicate.segments),
            )

        original_filename = display_filename(row)
        mime_type = mimetypes.guess_type(row.path.name)[0] or "video/mp4"
        asset = Asset(
            original_filename=original_filename[:255],
            stored_filename="pending",
            file_path="pending",
            mime_type=mime_type,
            file_size_bytes=row.path.stat().st_size,
            status=AssetStatus.UPLOADED.value,
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)

        destination = asset_upload_path(asset.id, row.path.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(row.path, destination)

        asset.stored_filename = destination.name
        asset.file_path = str(destination)
        try:
            metadata = probe_media(destination)
            asset.duration_seconds = metadata["duration_seconds"]
            asset.width = metadata["width"]
            asset.height = metadata["height"]
            asset.fps = metadata["fps"]
            asset.status = AssetStatus.READY.value
        except FFmpegError as exc:
            asset.status = AssetStatus.FAILED.value
            asset.error_message = str(exc)

        self.db.commit()
        self.db.refresh(asset)

        segment_count = 0
        segment_message = None
        if self.segment_seconds and asset.status == AssetStatus.READY.value:
            try:
                segment_count = self.segment_asset(asset)
            except FFmpegError as exc:
                segment_message = f"Imported, but segmentation failed: {exc}"

        if self._asset_hashes is not None:
            self._asset_hashes[file_sha256(destination)] = asset

        return ImportResult(
            source_path=str(row.path),
            action="imported",
            target_type="asset",
            target_id=asset.id,
            status=asset.status,
            segments=segment_count,
            message=asset.error_message if asset.status == AssetStatus.FAILED.value else segment_message,
        )

    def import_creative_reference(self, row: ImportRow) -> ImportResult:
        title = row.title or row.path.stem
        source_url = row.path.resolve().as_uri()
        reference = self.db.scalar(
            select(CreativeReference).where(CreativeReference.source_url == source_url)
        )
        action = "updated"
        metadata = {
            "source_url": source_url,
            "source_site": "local_file",
            "title": title[:255],
            "description": row.notes,
            "image_url": source_url if is_image_file(row.path) else None,
            "rights_status": normalize_rights_status(row.rights_status),
            "component_type": "ad_sample",
            "industry": row.industry,
            "style_tags": row.tags or [],
            "layout_json": {
                "local_path": str(row.path),
                "media_kind": media_kind(row.path),
            },
            "notes": row.notes,
            "is_active": True,
        }

        if reference is None:
            reference = CreativeReference(**metadata)
            self.db.add(reference)
            action = "imported"
        else:
            for key, value in metadata.items():
                setattr(reference, key, value)

        self.db.commit()
        self.db.refresh(reference)
        return ImportResult(
            source_path=str(row.path),
            action=action,
            target_type="creative_reference",
            target_id=reference.id,
            status="ready",
        )

    def find_duplicate_asset(self, path: Path) -> Optional[Asset]:
        if self.dedupe == "off":
            return None
        if self.dedupe == "filename":
            return self.db.scalar(
                select(Asset).where(Asset.original_filename == path.name).limit(1)
            )
        if self._asset_hashes is None:
            self._asset_hashes = {}
            for asset in self.db.scalars(select(Asset)):
                asset_path = Path(asset.file_path)
                if asset_path.exists() and asset_path.is_file():
                    self._asset_hashes[file_sha256(asset_path)] = asset
        return self._asset_hashes.get(file_sha256(path))

    def segment_asset(self, asset: Asset) -> int:
        if not asset.duration_seconds:
            return 0

        for existing in list(asset.segments):
            self.db.delete(existing)
        self.db.flush()

        generated_segments = split_fixed_segments(
            source_path=Path(asset.file_path),
            output_dir=asset_segments_dir(asset.id),
            duration_seconds=asset.duration_seconds,
            segment_seconds=self.segment_seconds or 3.0,
        )
        segments = []
        for item in generated_segments:
            segment = Segment(
                asset_id=asset.id,
                segment_index=item["index"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                duration_seconds=item["duration_seconds"],
                file_path=item["file_path"],
                detection_method="fixed_interval",
                status=SegmentStatus.READY.value,
            )
            self.db.add(segment)
            segments.append(segment)
        self.db.commit()
        return len(segments)


def read_manifest(manifest_path: Path, source_root: Path, default_kind: str) -> list[ImportRow]:
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")
    rows = []
    with manifest_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for index, raw in enumerate(reader, start=2):
            filename = raw.get("filename") or raw.get("path") or raw.get("file")
            if not filename:
                raise SystemExit(f"Manifest row {index} is missing filename/path.")
            path = Path(filename).expanduser()
            if not path.is_absolute():
                path = source_root / path
            path = path.resolve()
            if not path.exists() or not path.is_file():
                print(f"skip missing file from manifest row {index}: {path}")
                continue
            rows.append(
                ImportRow(
                    path=path,
                    usage_type=raw.get("usage_type") or default_kind,
                    title=empty_to_none(raw.get("title")),
                    rights_status=empty_to_none(raw.get("rights_status")),
                    industry=empty_to_none(raw.get("industry")),
                    tags=parse_tags(raw.get("tags")),
                    notes=empty_to_none(raw.get("notes")),
                )
            )
    return rows


def discover_rows(source: Path, default_kind: str, *, recursive: bool) -> list[ImportRow]:
    files = [source] if source.is_file() else discover_files(source, recursive=recursive)
    return [
        ImportRow(path=path.resolve(), usage_type=default_kind, title=None)
        for path in files
        if is_importable_file(path)
    ]


def discover_files(source: Path, *, recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    return sorted(path for path in source.glob(pattern) if path.is_file())


def dry_run(rows: Iterable[ImportRow]) -> list[ImportResult]:
    results = []
    for row in rows:
        usage_type = normalize_usage_type(row.usage_type)
        target_type = "asset" if usage_type == "production_asset" else "creative_reference"
        action = "would_import"
        message = None
        if usage_type == "production_asset" and not is_video_file(row.path):
            action = "would_skip"
            message = "Production assets must be video files."
        results.append(
            ImportResult(
                source_path=str(row.path),
                action=action,
                target_type=target_type,
                status="dry_run",
                message=message,
            )
        )
    return results


def print_summary(results: list[ImportResult]) -> None:
    counts: dict[str, int] = {}
    for result in results:
        key = result.action
        counts[key] = counts.get(key, 0) + 1
        target = f" {result.target_type}#{result.target_id}" if result.target_id else ""
        segments = f" segments={result.segments}" if result.segments else ""
        message = f" - {result.message}" if result.message else ""
        print(f"{result.action}: {result.source_path}{target} [{result.status}]{segments}{message}")
    print("summary:", ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def is_importable_file(path: Path) -> bool:
    return path.suffix.lower() in DEFAULT_EXTENSIONS


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def media_kind(path: Path) -> str:
    if is_video_file(path):
        return "video"
    if is_image_file(path):
        return "image"
    return "file"


def display_filename(row: ImportRow) -> str:
    if not row.title:
        return row.path.name
    title = row.title.strip()
    if Path(title).suffix:
        return title
    return f"{title}{row.path.suffix}"


def normalize_usage_type(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in PRODUCTION_USAGE:
        return "production_asset"
    if normalized in REFERENCE_USAGE:
        return "reference_only"
    raise ValueError(
        f"Unsupported usage_type {value!r}; use production_asset or reference_only."
    )


def normalize_rights_status(value: Optional[str]) -> str:
    normalized = (value or "reference_only").strip().lower()
    allowed = {
        "reference_only",
        "needs_review",
        "licensed",
        "owned",
        "public_domain",
        "cc_by",
    }
    return normalized if normalized in allowed else "reference_only"


def parse_tags(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [tag.strip() for tag in value.replace("，", ",").split(",") if tag.strip()]


def empty_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


if __name__ == "__main__":
    main()
