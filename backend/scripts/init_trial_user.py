import argparse
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.models import User
from app.services.auth import hash_password, normalize_phone


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a trial user.")
    parser.add_argument("--phone", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--display-name", default="Trial operator")
    parser.add_argument(
        "--update-password",
        action="store_true",
        help="Update the password when the phone already exists.",
    )
    args = parser.parse_args()

    init_db()
    phone = normalize_phone(args.phone)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.phone == phone))
        if user is None:
            user = User(
                phone=phone,
                password_hash=hash_password(args.password),
                display_name=args.display_name,
                is_active=True,
            )
            db.add(user)
            db.commit()
            print(f"Created trial user: {phone}")
            return

        user.display_name = args.display_name or user.display_name
        user.is_active = True
        if args.update_password:
            user.password_hash = hash_password(args.password)
        db.commit()
        print(f"Updated trial user: {phone}")


if __name__ == "__main__":
    main()
