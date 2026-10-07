"""Keep one person from being punched twice while they are still at the camera."""
from datetime import datetime, timedelta, timezone
from threading import Lock

from backend.app.config import settings

RELEASE_MISSES = 8
FRAME_GAP = timedelta(seconds=3)

_lock = Lock()
_held: dict[int, dict] = {}
_claims: set[int] = set()
_last_noted: datetime | None = None


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def clear_desk() -> None:
    global _last_noted
    with _lock:
        _held.clear()
        _claims.clear()
        _last_noted = None


def match_band(distance: float) -> str:
    """A sure match can punch itself. A close match waits for someone to confirm."""
    limit = settings.auto_match_threshold
    if limit > settings.match_threshold:
        limit = settings.match_threshold
    return "sure" if float(distance) <= limit else "close"


def claim_punch(employee_id: int) -> bool:
    with _lock:
        if employee_id in _held or employee_id in _claims:
            return False
        _claims.add(employee_id)
        return True


def complete_punch(employee_id: int, seconds: int, now: datetime | None = None) -> None:
    moment = _now(now)
    with _lock:
        _claims.discard(employee_id)
        _held[employee_id] = {"missed": 0, "until": moment + timedelta(seconds=max(0, seconds))}


def release_claim(employee_id: int) -> None:
    with _lock:
        _claims.discard(employee_id)


def punch_blocked(employee_id: int) -> bool:
    with _lock:
        return employee_id in _held or employee_id in _claims


def note_seen(seen_ids: set[int], now: datetime | None = None) -> None:
    """Drop a hold after the cooldown once the face has left, including a camera gap."""
    global _last_noted
    moment = _now(now)
    with _lock:
        gap = _last_noted is not None and moment - _last_noted > FRAME_GAP
        _last_noted = moment
        for employee_id, row in list(_held.items()):
            if gap:
                row["missed"] = RELEASE_MISSES
            if employee_id in seen_ids and not gap:
                row["missed"] = 0
                continue
            if not gap:
                row["missed"] += 1
            if row["missed"] >= RELEASE_MISSES and row["until"] <= moment:
                del _held[employee_id]
