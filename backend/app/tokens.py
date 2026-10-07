"""Short-lived proof that the server just matched an employee."""
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from threading import Lock

from backend.app.config import settings

_lock = Lock()
_tokens: dict[str, dict] = {}


def issue_match_token(user_id: int, employee_id: int, distance: float) -> str:
    token = token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.match_token_seconds)
    with _lock:
        _tokens[token] = {
            "user_id": user_id,
            "employee_id": employee_id,
            "distance": float(distance),
            "expires_at": expires_at,
        }
    return token


def consume_match_token(token: str, user_id: int) -> dict | None:
    now = datetime.now(timezone.utc)
    with _lock:
        row = _tokens.get(token)
        if row is None or row["user_id"] != user_id or row["expires_at"] <= now:
            return None
        return _tokens.pop(token)


_undos: dict[str, dict] = {}


def issue_undo_token(user_id: int, attendance_id: int, action: str) -> str:
    token = token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.undo_seconds)
    with _lock:
        _undos[token] = {
            "user_id": user_id,
            "attendance_id": attendance_id,
            "action": action,
            "expires_at": expires_at,
        }
    return token


def consume_undo_token(token: str, user_id: int) -> dict | None:
    now = datetime.now(timezone.utc)
    with _lock:
        row = _undos.get(token)
        if row is None or row["user_id"] != user_id or row["expires_at"] <= now:
            return None
        return _undos.pop(token)


def restore_undo_token(token: str, row: dict) -> None:
    if row["expires_at"] <= datetime.now(timezone.utc):
        return
    with _lock:
        _undos[token] = row
