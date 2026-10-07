"""Employees ask for a missed punch. Admins approve it."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from backend.app.correct import apply_correction, clean_note, prepare_clocks
from backend.app.db import get_db
from backend.app.models import CorrectionRequest, Employee, User
from backend.app.schemas import CorrectionRequestCreate
from backend.app.security import require_active, require_staff
from backend.app.workday import local_now

router = APIRouter(prefix="/corrections")


def correction_out(row: CorrectionRequest) -> dict:
    employee = row.employee
    reviewed = row.reviewed_at.isoformat() if row.reviewed_at is not None else None
    created = row.created_at.isoformat() if row.created_at is not None else None
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "employee_name": employee.name if employee is not None else "",
        "local_date": row.local_date,
        "check_in": row.check_in,
        "check_out": row.check_out,
        "note": row.note,
        "status": row.status,
        "reviewed_at": reviewed,
        "created_at": created,
    }


@router.get("")
def list_corrections(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    query = db.query(CorrectionRequest).options(joinedload(CorrectionRequest.employee))
    if user.role == "employee":
        if user.employee is None:
            return []
        query = query.filter(CorrectionRequest.employee_id == user.employee.id)
    if status_filter:
        query = query.filter(CorrectionRequest.status == status_filter)
    rows = query.order_by(CorrectionRequest.created_at.desc()).all()
    return [correction_out(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def request_correction(
    body: CorrectionRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    if user.employee is None:
        raise HTTPException(status_code=400, detail="This account has no employee profile")
    note = clean_note(body.note)
    day, check_in, check_out = prepare_clocks(body.local_date, body.check_in, body.check_out, today=local_now().date())
    employee = db.get(Employee, user.employee.id)
    if employee is None:
        raise HTTPException(status_code=400, detail="This account has no employee profile")
    pending = (
        db.query(CorrectionRequest)
        .filter(
            CorrectionRequest.employee_id == employee.id,
            CorrectionRequest.local_date == day.isoformat(),
            CorrectionRequest.status == "pending",
        )
        .first()
    )
    if pending is not None:
        raise HTTPException(status_code=409, detail="You already have a correction waiting for that day")
    row = CorrectionRequest(
        employee_id=employee.id,
        local_date=day.isoformat(),
        check_in=check_in or None,
        check_out=check_out or None,
        note=note,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return correction_out(row)


def review(correction_id: int, decision: str, db: Session, user: User) -> dict:
    row = db.query(CorrectionRequest).options(joinedload(CorrectionRequest.employee)).filter(CorrectionRequest.id == correction_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Correction request not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="That request was already reviewed")
    if decision == "approved":
        employee = row.employee
        if employee is None:
            raise HTTPException(status_code=400, detail="That employee is no longer on the roster")
        day, check_in, check_out = prepare_clocks(
            row.local_date,
            row.check_in,
            row.check_out,
            today=local_now().date(),
            allow_future=True,
        )
        apply_correction(db, employee, day, check_in, check_out, row.note, user.id)
        row = db.get(CorrectionRequest, correction_id)
        if row is None:
            raise HTTPException(status_code=400, detail="Correction request not found")
    row.status = decision
    row.reviewed_by = user.id
    row.reviewed_at = local_now()
    db.commit()
    db.refresh(row)
    return correction_out(row)


@router.post("/{correction_id}/approve")
def approve(correction_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    return review(correction_id, "approved", db, user)


@router.post("/{correction_id}/reject")
def reject(correction_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    return review(correction_id, "rejected", db, user)
