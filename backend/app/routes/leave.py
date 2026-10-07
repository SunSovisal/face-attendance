"""Leave requests."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from backend.app.db import get_db
from backend.app.models import Employee, LeaveRequest, User
from backend.app.schemas import LeaveCreate
from backend.app.security import require_active, require_staff
from backend.app.workday import local_now

router = APIRouter(prefix="/leave")
TYPES = {"annual", "sick", "unpaid"}


def parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Use dates like YYYY-MM-DD") from None


def leave_out(row: LeaveRequest) -> dict:
    employee = row.employee
    reviewed = row.reviewed_at.isoformat() if row.reviewed_at is not None else None
    created = row.created_at.isoformat() if row.created_at is not None else None
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "employee_name": employee.name if employee is not None else "",
        "type": row.type,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "note": row.note,
        "status": row.status,
        "reviewed_at": reviewed,
        "created_at": created,
    }


@router.get("")
def list_leave(db: Session = Depends(get_db), user: User = Depends(require_active)):
    query = db.query(LeaveRequest).options(joinedload(LeaveRequest.employee))
    if user.role == "employee":
        if user.employee is None:
            return []
        query = query.filter(LeaveRequest.employee_id == user.employee.id)
    rows = query.order_by(LeaveRequest.created_at.desc()).all()
    return [leave_out(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def request_leave(body: LeaveCreate, db: Session = Depends(get_db), user: User = Depends(require_active)):
    if user.employee is None:
        raise HTTPException(status_code=400, detail="This account has no employee profile")
    if body.type not in TYPES:
        raise HTTPException(status_code=400, detail="Leave type must be annual, sick, or unpaid")
    start = parse_day(body.start_date)
    end = parse_day(body.end_date)
    if end < start:
        raise HTTPException(status_code=400, detail="The end date is before the start date")
    note = body.note.strip()
    if len(note) > 500:
        raise HTTPException(status_code=400, detail="Note is too long")
    overlap = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id == user.employee.id,
            LeaveRequest.status.in_(("pending", "approved")),
            LeaveRequest.start_date <= end.isoformat(),
            LeaveRequest.end_date >= start.isoformat(),
        )
        .first()
    )
    if overlap is not None:
        raise HTTPException(status_code=409, detail="Those dates overlap another request")
    row = LeaveRequest(
        employee_id=user.employee.id,
        type=body.type,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        note=note,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return leave_out(row)


def review(leave_id: int, decision: str, db: Session, user: User) -> dict:
    row = db.get(LeaveRequest, leave_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="That request was already reviewed")
    row.status = decision
    row.reviewed_by = user.id
    row.reviewed_at = local_now()
    db.commit()
    db.refresh(row)
    return leave_out(row)


@router.post("/{leave_id}/approve")
def approve(leave_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    return review(leave_id, "approved", db, user)


@router.post("/{leave_id}/reject")
def reject(leave_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    return review(leave_id, "rejected", db, user)
