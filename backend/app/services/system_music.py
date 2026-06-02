import math
import shutil
import struct
import wave
from pathlib import Path
from typing import Iterable, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MusicTrack
from app.services.storage import ensure_storage_dirs, storage_root


SAMPLE_RATE = 44_100
DURATION_SECONDS = 16.0

TrackSpec = Tuple[str, str, List[Tuple[float, float, float]]]
OPEN_MUSIC_DIR = Path(__file__).resolve().parents[1] / "assets" / "open_music"

SYSTEM_MUSIC_TRACKS: List[TrackSpec] = [
    (
        "System Bright Pulse",
        "system-bright-pulse.wav",
        [
            (261.63, 329.63, 392.0),
            (293.66, 369.99, 440.0),
            (329.63, 392.0, 493.88),
            (392.0, 493.88, 587.33),
        ],
    ),
    (
        "System Calm Bed",
        "system-calm-bed.wav",
        [
            (220.0, 277.18, 329.63),
            (196.0, 246.94, 293.66),
            (174.61, 220.0, 261.63),
            (196.0, 246.94, 329.63),
        ],
    ),
    (
        "System Clean Drive",
        "system-clean-drive.wav",
        [
            (329.63, 415.3, 493.88),
            (246.94, 311.13, 369.99),
            (293.66, 369.99, 440.0),
            (220.0, 277.18, 329.63),
        ],
    ),
    (
        "System Soft Resolve",
        "system-soft-resolve.wav",
        [
            (174.61, 261.63, 329.63),
            (196.0, 293.66, 349.23),
            (220.0, 329.63, 392.0),
            (164.81, 246.94, 329.63),
        ],
    ),
]

OPEN_MUSIC_TRACKS = [
    {
        "title": "Speed Energy",
        "original_filename": "Speed Energy by WinnieTheMoog.ogg",
        "stored_filename": "open-winniethemoog-speed-energy.ogg",
        "duration_seconds": 104.832018,
        "artist": "WinnieTheMoog",
        "source_url": "https://commons.wikimedia.org/wiki/File:Speed_Energy_by_WinnieTheMoog.ogg",
        "attribution_text": '"Speed Energy" by WinnieTheMoog, licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/',
        "mood": "fast, sport, electronic",
    },
    {
        "title": "Street Trap",
        "original_filename": "WinnieTheMoog - Street Trap.ogg",
        "stored_filename": "open-winniethemoog-street-trap.ogg",
        "duration_seconds": 86.87127,
        "artist": "WinnieTheMoog",
        "source_url": "https://commons.wikimedia.org/wiki/File:WinnieTheMoog_-_Street_Trap.ogg",
        "attribution_text": '"Street Trap" by WinnieTheMoog, licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/',
        "mood": "fast, trap, adrenaline",
    },
    {
        "title": "Dubstep Loop",
        "original_filename": "Dubstep Loop by WinnieTheMoog.ogg",
        "stored_filename": "open-winniethemoog-dubstep-loop.ogg",
        "duration_seconds": 29.152653,
        "artist": "WinnieTheMoog",
        "source_url": "https://commons.wikimedia.org/wiki/File:Dubstep_Loop_by_WinnieTheMoog.ogg",
        "attribution_text": '"Dubstep Loop" by WinnieTheMoog, licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/',
        "mood": "fast, dubstep, loop",
    },
    {
        "title": "Justice And Fame",
        "original_filename": "Justice And Fame by Rafael Krux.ogg",
        "stored_filename": "open-rafael-krux-justice-and-fame.ogg",
        "duration_seconds": 130.063673,
        "artist": "Rafael Krux",
        "source_url": "https://commons.wikimedia.org/wiki/File:Justice_And_Fame_by_Rafael_Krux.ogg",
        "attribution_text": '"Justice And Fame" by Rafael Krux, licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/',
        "mood": "epic, aggressive, action",
    },
    {
        "title": "The Epic 2",
        "original_filename": "Rafael Krux - The Epic 2.ogg",
        "stored_filename": "open-rafael-krux-the-epic-2.ogg",
        "duration_seconds": 170.657959,
        "artist": "Rafael Krux",
        "source_url": "https://commons.wikimedia.org/wiki/File:Rafael_Krux_-_The_Epic_2.ogg",
        "attribution_text": '"The Epic 2" by Rafael Krux, licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/',
        "mood": "epic, uplifting, action",
    },
    {
        "title": "Epic Trailer",
        "original_filename": "Epic Trailer by Rafael Krux.ogg",
        "stored_filename": "open-rafael-krux-epic-trailer.ogg",
        "duration_seconds": 128.641066,
        "artist": "Rafael Krux",
        "source_url": "https://commons.wikimedia.org/wiki/File:Epic_Trailer_by_Rafael_Krux.ogg",
        "attribution_text": '"Epic Trailer" by Rafael Krux, licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/',
        "mood": "epic, trailer, action",
    },
    {
        "title": "Dramatic Trailer",
        "original_filename": "Dramatic Trailer by Rafael Krux.ogg",
        "stored_filename": "open-rafael-krux-dramatic-trailer.ogg",
        "duration_seconds": 97.959184,
        "artist": "Rafael Krux",
        "source_url": "https://commons.wikimedia.org/wiki/File:Dramatic_Trailer_by_Rafael_Krux.ogg",
        "attribution_text": '"Dramatic Trailer" by Rafael Krux, licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/',
        "mood": "powerful, dramatic, trailer",
    },
    {
        "title": "Fantasy Chamber Adventure",
        "original_filename": "Fantasy Chamber Adventure by Rafael Krux.ogg",
        "stored_filename": "open-rafael-krux-fantasy-chamber-adventure.ogg",
        "duration_seconds": 131.410045,
        "artist": "Rafael Krux",
        "source_url": "https://commons.wikimedia.org/wiki/File:Fantasy_Chamber_Adventure_by_Rafael_Krux.ogg",
        "attribution_text": '"Fantasy Chamber Adventure" by Rafael Krux, licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/',
        "mood": "adventure, cinematic, action",
    },
]


def seed_generated_system_music(db: Session) -> int:
    ensure_storage_dirs()
    music_dir = storage_root() / "music"
    music_dir.mkdir(parents=True, exist_ok=True)

    for title, filename, progression in SYSTEM_MUSIC_TRACKS:
        path = music_dir / filename
        if not path.exists() or path.stat().st_size == 0:
            write_track(path=path, progression=progression)
        track = db.scalar(
            select(MusicTrack).where(
                MusicTrack.title == title,
                MusicTrack.scope == "system",
            )
        )
        if track is None:
            track = MusicTrack(
                user_id=None,
                title=title,
                original_filename=filename,
                stored_filename=filename,
                file_path=str(path),
                mime_type="audio/wav",
                scope="system",
                is_active=True,
            )
            db.add(track)
        track.stored_filename = filename
        track.file_path = str(path)
        track.file_size_bytes = path.stat().st_size
        track.duration_seconds = DURATION_SECONDS
        track.artist = "Flashcutter"
        track.license_name = "Internal generated test audio"
        track.license_url = None
        track.source_url = None
        track.attribution_text = "Generated by Flashcutter for local MVP testing."
        track.mood = "test"
        track.bpm = None
        track.is_active = True
    seed_open_music_tracks(db=db, music_dir=music_dir)
    db.commit()
    return len(SYSTEM_MUSIC_TRACKS) + len(OPEN_MUSIC_TRACKS)


def seed_open_music_tracks(db: Session, music_dir: Path) -> None:
    if not OPEN_MUSIC_DIR.exists():
        return

    for spec in OPEN_MUSIC_TRACKS:
        filename = str(spec["stored_filename"])
        source = OPEN_MUSIC_DIR / filename
        if not source.exists():
            continue
        path = music_dir / filename
        if not path.exists() or path.stat().st_size != source.stat().st_size:
            shutil.copyfile(source, path)

        track = db.scalar(select(MusicTrack).where(MusicTrack.stored_filename == filename))
        if track is None:
            track = MusicTrack(
                user_id=None,
                title=str(spec["title"]),
                original_filename=str(spec["original_filename"]),
                stored_filename=filename,
                file_path=str(path),
                mime_type="audio/ogg",
                scope="system",
                is_active=True,
            )
            db.add(track)
        track.user_id = None
        track.title = str(spec["title"])
        track.original_filename = str(spec["original_filename"])
        track.file_path = str(path)
        track.mime_type = "audio/ogg"
        track.file_size_bytes = path.stat().st_size
        track.duration_seconds = float(spec["duration_seconds"])
        track.scope = "system"
        track.artist = str(spec["artist"])
        track.license_name = "CC BY 4.0"
        track.license_url = "https://creativecommons.org/licenses/by/4.0/"
        track.source_url = str(spec["source_url"])
        track.attribution_text = str(spec["attribution_text"])
        track.mood = str(spec["mood"])
        track.bpm = None
        track.is_active = True


def write_track(path: Path, progression: Iterable[Tuple[float, float, float]]) -> None:
    chords = list(progression)
    total_samples = int(SAMPLE_RATE * DURATION_SECONDS)
    chord_samples = max(1, total_samples // len(chords))

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for sample_index in range(total_samples):
            t = sample_index / SAMPLE_RATE
            chord = chords[min(sample_index // chord_samples, len(chords) - 1)]
            local = (sample_index % chord_samples) / chord_samples
            envelope = smooth_envelope(local)
            beat = 0.55 + 0.45 * max(0.0, math.sin(2 * math.pi * 2 * t))
            value = 0.0
            for frequency in chord:
                value += math.sin(2 * math.pi * frequency * t) * 0.18
                value += math.sin(2 * math.pi * frequency * 2 * t) * 0.035
            bass_frequency = chord[0] / 2
            value += math.sin(2 * math.pi * bass_frequency * t) * 0.22 * beat
            sample = int(max(-0.92, min(0.92, value * envelope)) * 32767)
            wav.writeframes(struct.pack("<h", sample))


def smooth_envelope(local: float) -> float:
    attack = min(1.0, local / 0.08)
    release = min(1.0, (1.0 - local) / 0.12)
    return max(0.0, min(1.0, attack, release))
