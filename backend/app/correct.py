"""Manual times, shared by an admin correction and an approved request."""
from datetime import date

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import AttendanceDay, Employee
from backend.app.sheet import persist_status
from backend.app.workday import as_local, at_clock, parse_clock


def normalize_clock(value: str) -> str:
    clock = parse_clock(value)
    return f"{clock.hour:02d}:{clock.minute:02d}"


def prepare_clocks(
    local_date: str,
    check_in: str | None,
    check_out: str | None,
    *,
    today: date,
    allow_future: bool = False,
) -> tuple[date, str, str]:
    try:
        day = date.fromisoformat(local_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD") from None
    if not allow_future and day > today:
        raise HTTPException(status_code=400, detail="That date is still in the future")
    arrival = (check_in or "").strip()
    leaving = (check_out or "").strip()
    if not arrival and not leaving:
        raise HTTPException(status_code=400, detail="Enter a check-in or a check-out time")
    try:
        if arrival:
            arrival = normalize_clock(arrival)
        if leaving:
            leaving = normalize_clock(leaving)
    except ValueError:
        raise HTTPException(status_code=400, detail="Use times like 08:00") from None
    return day, arrival, leaving


def clean_note(note: str) -> str:
    text = note.strip()
    if not text or len(text) > 500:
        raise HTTPException(status_code=400, detail="A reason is required")
    return text


def apply_correction(
    db: Session,
    employee: Employee,
    day: date,
    check_in: str,
    check_out: str,
    note: str,
    user_id: int,
) -> AttendanceDay:
    row = (
        db.query(AttendanceDay)
        .filter(AttendanceDay.employee_id == employee.id, AttendanceDay.local_date == day.isoformat())
        .one_or_none()
    )
    if row is None:
        row = AttendanceDay(employee_id=employee.id, employee_name=employee.name, local_date=day.isoformat(), note=note)
        db.add(row)
    row.employee_name = employee.name
    row.note = note
    if check_in:
        row.check_in_at = at_clock(day, check_in)
        row.check_in_manual = True
        row.check_in_by = user_id
    if check_out:
        row.check_out_at = at_clock(day, check_out)
        row.check_out_manual = True
        row.check_out_by = user_id
    if row.check_in_at is None:
        raise HTTPException(status_code=400, detail="Check-in is required before check-out")
    if row.check_out_at is not None and as_local(row.check_out_at) <= as_local(row.check_in_at):
        db.rollback()
        raise HTTPException(status_code=400, detail="Check-out must be after check-in")
    persist_status(db, row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That day already exists") from None
    db.refresh(row)
    return row
