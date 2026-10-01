"""Short-lived proof that the server just matched a person."""
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from threading import Lock

from backend.app.config import settings

_lock = Lock()
_tokens: dict[str, dict] = {}


def issue_match_token(admin_id: int, person_id: int, distance: float) -> str:
    token = token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.match_token_seconds)
    with _lock:
        _tokens[token] = {
            "admin_id": admin_id,
            "person_id": person_id,
            "distance": float(distance),
            "expires_at": expires_at,
        }
    return token


def consume_match_token(token: str, admin_id: int) -> dict | None:
    now = datetime.now(timezone.utc)
    with _lock:
        row = _tokens.get(token)
        if row is None or row["admin_id"] != admin_id or row["expires_at"] <= now:
            return None
        return _tokens.pop(token)