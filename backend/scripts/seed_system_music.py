import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.services.storage import ensure_storage_dirs
from app.services.system_music import seed_generated_system_music


def main() -> None:
    ensure_storage_dirs()
    init_db()
    with SessionLocal() as db:
        count = seed_generated_system_music(db)
    print(f"Seeded {count} generated system music tracks.")


if __name__ == "__main__":
    main()
