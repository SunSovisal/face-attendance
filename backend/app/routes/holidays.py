"""Office holidays."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Holiday, User
from backend.app.schemas import HolidayCreate
from backend.app.security import require_staff

router = APIRouter(prefix="/holidays")


def holiday_out(row: Holiday) -> dict:
    return {"id": row.id, "local_date": row.local_date, "name": row.name}


@router.get("")
def list_holidays(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    rows = db.query(Holiday).order_by(Holiday.local_date.desc()).all()
    return [holiday_out(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_holiday(body: HolidayCreate, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    name = body.name.strip()
    if not name or len(name) > 120:
        raise HTTPException(status_code=400, detail="Holiday name is required")
    try:
        day = date.fromisoformat(body.local_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Use a date like YYYY-MM-DD") from None
    if db.query(Holiday).filter(Holiday.local_date == day.isoformat()).one_or_none():
        raise HTTPException(status_code=409, detail="That date is already a holiday")
    row = Holiday(local_date=day.isoformat(), name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return holiday_out(row)


@router.delete("/{holiday_id}")
def delete_holiday(holiday_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    row = db.get(Holiday, holiday_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
