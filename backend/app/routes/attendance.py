"""Workdays, punches, corrections, and the today and month sheets."""
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.app.config import settings
from backend.app.correct import apply_correction, clean_note, prepare_clocks
from backend.app.csvout import attendance_table, csv_response, month_table
from backend.app.db import get_db
from backend.app.desk import claim_punch, complete_punch, release_claim
from backend.app.engine import decode_jpeg
from backend.app.models import AttendanceDay, Employee, FaceSample, User
from backend.app.schemas import Correction, UndoRequest
from backend.app.security import require_active, require_staff
from backend.app.sheet import build_days, get_office, month_rows, persist_status, punch_target
from backend.app.tokens import consume_match_token, consume_undo_token, issue_undo_token, restore_undo_token
from backend.app.workday import is_workday, local_now

router = APIRouter(prefix="/attendance")


def parse_day(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label} must be YYYY-MM-DD") from None


def month_bounds(month: str) -> tuple[date, date]:
    try:
        year_text, month_text = month.split("-")
        start = date(int(year_text), int(month_text), 1)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Month must be YYYY-MM") from None
    if start.month == 12:
        end = date(start.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(start.year, start.month + 1, 1) - timedelta(days=1)
    return start, end


def remove_snapshot(raw: str | None) -> None:
    if not raw:
        return
    path = Path(raw).resolve()
    root = settings.attendance_dir.resolve()
    if path.is_file() and root in path.parents:
        path.unlink()


def own_employee_id(user: User) -> int | None:
    if user.role != "employee":
        return None
    if user.employee is None:
        return -1
    return user.employee.id


def scoped_employee_id(user: User, requested: int | None) -> int | None:
    mine = own_employee_id(user)
    if mine is None:
        return requested
    return mine


@router.get("")
def list_attendance(
    employee_id: int | None = None,
    department_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    today = local_now().date()
    start = parse_day(from_date, "From") if from_date else today
    end = parse_day(to_date, "To") if to_date else today
    if end < start:
        raise HTTPException(status_code=400, detail="The end date is before the start date")
    chosen = scoped_employee_id(user, employee_id)
    if chosen == -1:
        return []
    return build_days(
        db,
        start,
        end,
        employee_id=chosen,
        department_id=None if user.role == "employee" else department_id,
        status=status_filter,
    )


@router.get("/export")
def export_attendance(
    employee_id: int | None = None,
    department_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    days = list_attendance(employee_id, department_id, status_filter, from_date, to_date, db, user)
    start = parse_day(from_date, "From") if from_date else local_now().date()
    end = parse_day(to_date, "To") if to_date else local_now().date()
    headers, rows = attendance_table(days)
    return csv_response(f"attendance-{start.isoformat()}-{end.isoformat()}.csv", headers, rows)


@router.get("/today")
def today_sheet(
    department_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    today = local_now().date()
    office = get_office(db)
    rows = build_days(db, today, today, department_id=department_id)
    counts = {"in": 0, "late": 0, "incomplete": 0, "left_early": 0, "absent": 0, "on_leave": 0, "due": 0}
    for row in rows:
        if row["check_in_at"]:
            counts["in"] += 1
        state = row["status"]
        if state in counts:
            counts[state] += 1
    holiday = next((row["detail"] for row in rows if row["status"] == "holiday" and row["detail"]), None)
    return {
        "local_date": today.isoformat(),
        "work_start": office.work_start,
        "work_end": office.work_end,
        "grace_minutes": office.grace_minutes,
        "office_closed": not is_workday(today, office.weekend_days),
        "holiday": holiday,
        "counts": counts,
        "rows": rows,
    }


@router.get("/month")
def month_sheet(
    month: str,
    department_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    start, end = month_bounds(month)
    employees = db.query(Employee).options(joinedload(Employee.user), joinedload(Employee.department)).all()
    enrolled = {row[0] for row in db.query(FaceSample.employee_id).distinct().all()}
    roster = [employee for employee in employees if employee.is_matchable(employee.id in enrolled)]
    if department_id is not None:
        roster = [employee for employee in roster if employee.department_id == department_id]
    days = build_days(db, start, end, department_id=department_id)
    return {"month": month, "rows": month_rows(days, roster)}


@router.get("/month/export")
def export_month(
    month: str,
    department_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    sheet = month_sheet(month, department_id, db, user)
    headers, rows = month_table(sheet["rows"])
    return csv_response(f"month-{month}.csv", headers, rows)


@router.get("/{attendance_id}/snapshot")
def attendance_snapshot(
    attendance_id: int,
    which: str = Query(default="in"),
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    row = db.get(AttendanceDay, attendance_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    if user.role == "employee" and (user.employee is None or row.employee_id != user.employee.id):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    raw_path = row.check_out_snapshot if which == "out" else row.check_in_snapshot
    if not raw_path:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    path = Path(raw_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(path, media_type="image/jpeg")


def save_snapshot(row_id: int, kind: str, raw: bytes) -> str:
    settings.attendance_dir.mkdir(parents=True, exist_ok=True)
    path = settings.attendance_dir / f"{row_id}-{kind}.jpg"
    path.write_bytes(raw)
    return str(path)


def day_view(db: Session, row: AttendanceDay) -> dict:
    day = date.fromisoformat(row.local_date)
    views = build_days(db, day, day, employee_id=row.employee_id)
    for view in views:
        if view["id"] == row.id:
            return view
    raise HTTPException(status_code=400, detail="Could not read that workday")


@router.post("/punch", status_code=status.HTTP_201_CREATED)
async def punch(
    match_token: str = Form(...),
    snapshot: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    raw = await snapshot.read()
    if decode_jpeg(raw) is None:
        raise HTTPException(status_code=400, detail="Snapshot is not a readable image")
    match = consume_match_token(match_token, user.id)
    if match is None:
        raise HTTPException(status_code=400, detail="Match token is missing or expired")
    employee = db.get(Employee, match["employee_id"])
    has_sample = (
        employee is not None and db.query(FaceSample.id).filter(FaceSample.employee_id == employee.id).first() is not None
    )
    if employee is None or not employee.is_matchable(has_sample):
        raise HTTPException(status_code=400, detail="This employee cannot be checked in")

    now = local_now()
    target, action = punch_target(db, employee.id, now.date())
    if action == "done":
        raise HTTPException(status_code=409, detail="Already checked out today")
    if not claim_punch(employee.id):
        raise HTTPException(status_code=409, detail="This person was just punched. They can punch again after they step away.")
    try:
        if action == "check_in":
            row = AttendanceDay(
                employee_id=employee.id,
                employee_name=employee.name,
                local_date=now.date().isoformat(),
                check_in_at=now,
                check_in_distance=match["distance"],
                check_in_by=user.id,
                check_in_manual=False,
            )
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(status_code=409, detail="Already checked in today") from None
            db.refresh(row)
            row.check_in_snapshot = save_snapshot(row.id, "in", raw)
        else:
            row = target
            if row is None:
                raise HTTPException(status_code=400, detail="There is no open check-in")
            row.check_out_at = now
            row.check_out_distance = match["distance"]
            row.check_out_by = user.id
            row.check_out_manual = False
            row.check_out_snapshot = save_snapshot(row.id, "out", raw)
        persist_status(db, row)
        db.commit()
        db.refresh(row)
        complete_punch(employee.id, settings.punch_cooldown_seconds)
        view = day_view(db, row)
        view["action"] = action
        view["undo_token"] = issue_undo_token(user.id, row.id, action)
        view["undo_seconds"] = settings.undo_seconds
        return view
    finally:
        release_claim(employee.id)


@router.post("/undo")
def undo(body: UndoRequest, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    token = body.undo_token
    match = consume_undo_token(token, user.id)
    if match is None:
        raise HTTPException(status_code=400, detail="That punch can no longer be undone")
    row = db.get(AttendanceDay, match["attendance_id"])
    action = match["action"]
    if row is None or action not in {"check_in", "check_out"}:
        raise HTTPException(status_code=400, detail="That punch can no longer be undone")
    try:
        if action == "check_in":
            if row.check_out_at is not None:
                raise HTTPException(status_code=400, detail="Check-out already happened")
            remove_snapshot(row.check_in_snapshot)
            employee_id = row.employee_id
            db.delete(row)
        else:
            if row.check_out_at is None:
                raise HTTPException(status_code=400, detail="Check-out is already gone")
            remove_snapshot(row.check_out_snapshot)
            employee_id = row.employee_id
            row.check_out_at = None
            row.check_out_distance = None
            row.check_out_snapshot = None
            row.check_out_by = None
            row.check_out_manual = False
            persist_status(db, row)
        db.commit()
    except Exception:
        db.rollback()
        restore_undo_token(token, match)
        raise
    if employee_id is not None:
        complete_punch(employee_id, settings.punch_cooldown_seconds)
    return {"ok": True, "action": action}


@router.post("/correct")
def correct(body: Correction, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    note = clean_note(body.note)
    day, check_in, check_out = prepare_clocks(
        body.local_date,
        body.check_in,
        body.check_out,
        today=local_now().date(),
        allow_future=True,
    )
    employee = db.get(Employee, body.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    row = apply_correction(db, employee, day, check_in, check_out, note, user.id)
    return day_view(db, row)
