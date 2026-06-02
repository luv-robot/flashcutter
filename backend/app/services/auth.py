import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

_SESSIONS: dict[str, tuple[int, datetime]] = {}
_TOKEN_TTL = timedelta(days=14)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    salt, _, expected = password_hash.partition("$")
    if not salt or not expected:
        return False
    actual = hash_password(password, salt).partition("$")[2]
    return secrets.compare_digest(actual, expected)


def create_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = (user.id, datetime.utcnow() + _TOKEN_TTL)
    return token


def user_for_token(db: Session, token: str) -> Optional[User]:
    session = _SESSIONS.get(token)
    if session is None:
        return None
    user_id, expires_at = session
    if expires_at <= datetime.utcnow():
        _SESSIONS.pop(token, None)
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def token_from_request(request: Request) -> Optional[str]:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    token = request.query_params.get("access_token")
    return token or None


def normalize_phone(phone: str) -> str:
    normalized = "".join(character for character in phone if character.isdigit() or character == "+")
    if len(normalized) < 6:
        raise HTTPException(status_code=400, detail="Phone number is too short")
    return normalized


def ensure_unique_phone(db: Session, phone: str) -> None:
    existing = db.scalar(select(User).where(User.phone == phone))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Phone number is already registered")
