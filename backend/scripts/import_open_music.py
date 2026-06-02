from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote, urlencode, urlparse, unquote
from urllib.request import Request, urlopen

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.models import MusicTrack
from app.services.ffmpeg import FFmpegError, probe_media
from app.services.storage import ensure_storage_dirs, storage_root


COMMONS_FILE_REDIRECT = "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
CC_BY_4_URL = "https://creativecommons.org/licenses/by/4.0/"


@dataclass(frozen=True)
class OpenMusicTrack:
    title: str
    commons_filename: str
    artist: str
    mood: str
    bpm: Optional[int]
    source_url: str
    license_name: str = "CC BY 4.0"
    license_url: str = CC_BY_4_URL

    @property
    def attribution_text(self) -> str:
        return (
            f'"{self.title}" by {self.artist}, licensed under {self.license_name}: '
            f"{self.license_url}"
        )


OPEN_MUSIC_TRACKS: list[OpenMusicTrack] = [
    OpenMusicTrack(
        title="Speed Energy",
        commons_filename="Speed Energy by WinnieTheMoog.ogg",
        artist="WinnieTheMoog",
        mood="fast, sport, electronic",
        bpm=150,
        source_url="https://commons.wikimedia.org/wiki/File:Speed_Energy_by_WinnieTheMoog.ogg",
    ),
    OpenMusicTrack(
        title="Street Trap",
        commons_filename="WinnieTheMoog - Street Trap.ogg",
        artist="WinnieTheMoog",
        mood="fast, trap, adrenaline",
        bpm=145,
        source_url="https://commons.wikimedia.org/wiki/File:WinnieTheMoog_-_Street_Trap.ogg",
    ),
    OpenMusicTrack(
        title="Dubstep Loop",
        commons_filename="Dubstep Loop by WinnieTheMoog.ogg",
        artist="WinnieTheMoog",
        mood="fast, dubstep, loop",
        bpm=140,
        source_url="https://commons.wikimedia.org/wiki/File:Dubstep_Loop_by_WinnieTheMoog.ogg",
    ),
    OpenMusicTrack(
        title="Justice And Fame",
        commons_filename="Justice And Fame by Rafael Krux.ogg",
        artist="Rafael Krux",
        mood="epic, aggressive, action",
        bpm=132,
        source_url="https://commons.wikimedia.org/wiki/File:Justice_And_Fame_by_Rafael_Krux.ogg",
    ),
    OpenMusicTrack(
        title="The Epic 2",
        commons_filename="Rafael Krux - The Epic 2.ogg",
        artist="Rafael Krux",
        mood="epic, uplifting, action",
        bpm=128,
        source_url="https://commons.wikimedia.org/wiki/File:Rafael_Krux_-_The_Epic_2.ogg",
    ),
    OpenMusicTrack(
        title="Epic Trailer",
        commons_filename="Epic Trailer by Rafael Krux.ogg",
        artist="Rafael Krux",
        mood="epic, trailer, action",
        bpm=126,
        source_url="https://commons.wikimedia.org/wiki/File:Epic_Trailer_by_Rafael_Krux.ogg",
    ),
    OpenMusicTrack(
        title="Dramatic Trailer",
        commons_filename="Dramatic Trailer by Rafael Krux.ogg",
        artist="Rafael Krux",
        mood="powerful, dramatic, trailer",
        bpm=124,
        source_url="https://commons.wikimedia.org/wiki/File:Dramatic_Trailer_by_Rafael_Krux.ogg",
    ),
    OpenMusicTrack(
        title="Fantasy Chamber Adventure",
        commons_filename="Fantasy Chamber Adventure by Rafael Krux.ogg",
        artist="Rafael Krux",
        mood="adventure, cinematic, action",
        bpm=120,
        source_url="https://commons.wikimedia.org/wiki/File:Fantasy_Chamber_Adventure_by_Rafael_Krux.ogg",
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download CC BY open music tracks into the system music library."
    )
    parser.add_argument("--limit", type=int, default=None, help="Import only the first N tracks.")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Re-download existing files and refresh metadata.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned imports only.")
    args = parser.parse_args()

    tracks = OPEN_MUSIC_TRACKS[: args.limit] if args.limit else OPEN_MUSIC_TRACKS
    if args.dry_run:
        for track in tracks:
            print(f"{track.title} — {track.artist} — {track.license_name} — {track.source_url}")
        return

    init_db()
    ensure_storage_dirs()
    music_dir = storage_root() / "music"
    music_dir.mkdir(parents=True, exist_ok=True)

    imported = 0
    with SessionLocal() as db:
        for track in tracks:
            record = db.scalar(
                select(MusicTrack).where(
                    MusicTrack.scope == "system",
                    MusicTrack.source_url == track.source_url,
                )
            )
            if record is None:
                record = db.scalar(
                    select(MusicTrack).where(
                        MusicTrack.scope == "system",
                        MusicTrack.title == track.title,
                        MusicTrack.artist == track.artist,
                    )
                )
            destination = music_dir / f"open-{slugify(track.artist)}-{slugify(track.title)}.ogg"
            if args.replace or not destination.exists() or destination.stat().st_size == 0:
                download_commons_file(track.commons_filename, destination)
                time.sleep(1.0)

            if record is None:
                record = MusicTrack(
                    user_id=None,
                    title=track.title,
                    original_filename=track.commons_filename,
                    stored_filename=destination.name,
                    file_path=str(destination),
                    mime_type="audio/ogg",
                    scope="system",
                    is_active=True,
                )
                db.add(record)
            apply_metadata(record, track, destination)
            imported += 1
        db.commit()

    print(f"Imported {imported} open music tracks into {music_dir}")


def download_commons_file(filename: str, destination: Path) -> None:
    url = commons_download_url(filename)
    request = Request(url, headers={"User-Agent": "Flashcutter/0.1 open music importer"})
    with urlopen(request, timeout=45) as response:
        content_type = response.headers.get("Content-Type", "")
        if content_type and not content_type.startswith(("audio/", "application/ogg")):
            raise RuntimeError(f"Unexpected content type for {filename}: {content_type}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def commons_download_url(filename: str) -> str:
    title = f"File:{filename}"
    query = urlencode(
        {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|mime",
        }
    )
    request = Request(
        f"{COMMONS_API_URL}?{query}",
        headers={"User-Agent": "Flashcutter/0.1 open music importer"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            imageinfo = page.get("imageinfo") or []
            if imageinfo and imageinfo[0].get("url"):
                return str(imageinfo[0]["url"])
    except Exception:
        pass
    return COMMONS_FILE_REDIRECT + quote(filename)


def apply_metadata(record: MusicTrack, track: OpenMusicTrack, path: Path) -> None:
    record.title = track.title
    record.original_filename = track.commons_filename
    record.stored_filename = path.name
    record.file_path = str(path)
    record.mime_type = mimetypes.guess_type(path.name)[0] or "audio/ogg"
    record.file_size_bytes = path.stat().st_size
    try:
        record.duration_seconds = probe_media(path).get("duration_seconds")
    except FFmpegError:
        record.duration_seconds = None
    record.scope = "system"
    record.is_active = True
    record.artist = track.artist
    record.license_name = track.license_name
    record.license_url = track.license_url
    record.source_url = track.source_url
    record.attribution_text = track.attribution_text
    record.mood = track.mood
    record.bpm = track.bpm


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "track"


if __name__ == "__main__":
    main()
