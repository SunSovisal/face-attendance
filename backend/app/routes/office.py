"""The single office schedule."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import User
from backend.app.schemas import OfficeUpdate
from backend.app.security import require_active, require_super
from backend.app.sheet import get_office, office_out
from backend.app.workday import join_weekend, parse_clock, validate_office

router = APIRouter(prefix="/office")


@router.get("")
def read_office(db: Session = Depends(get_db), _: User = Depends(require_active)):
    return office_out(get_office(db))


@router.put("")
def update_office(body: OfficeUpdate, db: Session = Depends(get_db), _: User = Depends(require_super)):
    problem = validate_office(body.work_start, body.work_end, body.grace_minutes, body.weekend_days)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    row = get_office(db)
    start = parse_clock(body.work_start.strip())
    end = parse_clock(body.work_end.strip())
    row.work_start = f"{start.hour:02d}:{start.minute:02d}"
    row.work_end = f"{end.hour:02d}:{end.minute:02d}"
    row.grace_minutes = body.grace_minutes
    row.weekend_days = join_weekend(body.weekend_days)
    db.commit()
    db.refresh(row)
    return office_out(row)
