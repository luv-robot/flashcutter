#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.models import CreativeReference
from app.services.creative_reference_importer import importable_metadata_for_url
from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import external ad/poster pages as reference-only template components."
    )
    parser.add_argument("urls", nargs="+", help="Creative reference URLs to import")
    parser.add_argument("--component-type", default=None)
    parser.add_argument("--industry", default=None)
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--notes", default=None)
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        for url in args.urls:
            metadata = importable_metadata_for_url(url)
            if args.component_type:
                metadata["component_type"] = args.component_type
            if args.industry:
                metadata["industry"] = args.industry
            if args.tag:
                metadata["style_tags"] = args.tag
            if args.notes:
                existing_notes = metadata.get("notes")
                metadata["notes"] = (
                    f"{args.notes}\n{existing_notes}" if existing_notes else args.notes
                )

            reference = db.scalar(
                select(CreativeReference).where(CreativeReference.source_url == url)
            )
            action = "updated"
            if reference is None:
                reference = CreativeReference(**metadata)
                db.add(reference)
                action = "created"
            else:
                for key, value in metadata.items():
                    setattr(reference, key, value)
            db.commit()
            db.refresh(reference)
            print(f"{action}: #{reference.id} {reference.title} [{reference.rights_status}]")


if __name__ == "__main__":
    main()
