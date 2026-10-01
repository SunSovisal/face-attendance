"""Confirmed attendance log."""
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.models import Admin, Attendance, Person
from backend.app.schemas import AttendanceConfirm
from backend.app.security import get_current_admin
from backend.app.tokens import consume_match_token

router = APIRouter(prefix="/attendance")


def local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def attendance_out(row: Attendance) -> dict:
    timestamp = row.timestamp.isoformat() if row.timestamp is not None else None
    return {
        "id": row.id,
        "person_id": row.person_id,
        "person_name": row.person_name,
        "timestamp": timestamp,
        "local_date": row.local_date,
        "distance": row.distance,
    }


@router.get("")
def list_attendance(
    person_id: int | None = None,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    query = db.query(Attendance)
    if person_id is not None:
        query = query.filter(Attendance.person_id == person_id)
    if from_date is not None:
        query = query.filter(Attendance.local_date >= from_date)
    if to_date is not None:
        query = query.filter(Attendance.local_date <= to_date)
    rows = query.order_by(Attendance.timestamp.desc()).all()
    return [attendance_out(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def confirm_attendance(
    body: AttendanceConfirm,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    match = consume_match_token(body.match_token, admin.id)
    if match is None:
        raise HTTPException(status_code=400, detail="Match token is missing or expired")
    person = db.get(Person, match["person_id"])
    if person is None:
        raise HTTPException(status_code=400, detail="Person no longer exists")

    now = local_now()
    row = Attendance(
        person_id=person.id,
        person_name=person.name,
        timestamp=now,
        local_date=now.strftime("%Y-%m-%d"),
        distance=match["distance"],
        admin_id=admin.id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Already logged today")
    db.refresh(row)
    return attendance_out(row)