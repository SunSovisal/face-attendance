"""How a calendar day becomes a work status."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from backend.app.config import settings

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def zone() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


def local_now() -> datetime:
    return datetime.now(zone())


def as_local(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=zone())
    return value.astimezone(zone())


def parse_clock(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise ValueError(value)
    return time(int(parts[0]), int(parts[1]))


def at_clock(day: date, clock: str) -> datetime:
    return datetime.combine(day, parse_clock(clock), tzinfo=zone())


def parse_weekend(value: str) -> set[str]:
    return {part.strip().lower()[:3] for part in value.split(",") if part.strip()}


def is_workday(day: date, weekend_days: str) -> bool:
    return WEEKDAYS[day.weekday()] not in parse_weekend(weekend_days)


def join_weekend(days: list[str]) -> str:
    chosen = set(days)
    return ",".join(day for day in WEEKDAYS if day in chosen)


def validate_office(work_start: str, work_end: str, grace_minutes: int, weekend_days: list[str]) -> str | None:
    try:
        start = parse_clock(work_start)
        end = parse_clock(work_end)
    except (ValueError, TypeError):
        return "Use times like 08:00"
    if start >= end:
        return "Work end must be after work start"
    if grace_minutes < 0 or grace_minutes > 180:
        return "Grace must be between 0 and 180 minutes"
    if any(day not in WEEKDAYS for day in weekend_days):
        return "Weekend days must be weekdays written as mon through sun"
    return None


def date_range(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def classify(
    *,
    day: date,
    check_in: datetime | None,
    check_out: datetime | None,
    work_start: str,
    work_end: str,
    grace_minutes: int,
    weekend_days: str,
    holiday: bool,
    on_leave: bool,
    now: datetime,
) -> dict:
    check_in = as_local(check_in)
    check_out = as_local(check_out)
    now = as_local(now) or local_now()
    start = at_clock(day, work_start)
    end = at_clock(day, work_end)
    late_minutes = 0
    early_minutes = 0
    worked_minutes = 0
    if check_in is not None and check_out is not None and check_out > check_in:
        worked_minutes = int((check_out - check_in).total_seconds() // 60)
    if check_in is not None and check_in > start + timedelta(minutes=grace_minutes):
        late_minutes = int((check_in - start).total_seconds() // 60)
    if check_out is not None and check_out < end:
        early_minutes = int((end - check_out).total_seconds() // 60)

    if holiday:
        status = "holiday"
    elif on_leave:
        status = "on_leave"
    elif check_in is None:
        workday = is_workday(day, weekend_days)
        day_over = day < now.date() or (day == now.date() and now >= end)
        if workday and day_over:
            status = "absent"
        elif workday and day == now.date():
            status = "due"
        else:
            status = "off"
    elif check_out is None:
        status = "incomplete"
    elif late_minutes > 0:
        status = "late"
    elif early_minutes > 0:
        status = "left_early"
    else:
        status = "present"

    return {
        "status": status,
        "late_minutes": late_minutes,
        "early_minutes": early_minutes,
        "worked_minutes": worked_minutes,
    }
