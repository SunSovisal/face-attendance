"""Build the attendance sheet from punches, leave, holidays, and office hours."""
from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from backend.app.models import AttendanceDay, Employee, FaceSample, Holiday, LeaveRequest, OfficeSettings
from backend.app.workday import as_local, at_clock, classify, date_range, local_now


def get_office(db: Session) -> OfficeSettings:
    row = db.get(OfficeSettings, 1)
    if row is None:
        row = OfficeSettings(id=1, work_start="08:00", work_end="17:00", grace_minutes=10, weekend_days="sat,sun")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def office_out(row: OfficeSettings) -> dict:
    return {
        "work_start": row.work_start,
        "work_end": row.work_end,
        "grace_minutes": row.grace_minutes,
        "weekend_days": [part for part in row.weekend_days.split(",") if part],
    }


def sample_ids(db: Session) -> set[int]:
    rows = db.query(FaceSample.employee_id).distinct().all()
    return {row[0] for row in rows}


def punch_target(db: Session, employee_id: int, today: date) -> tuple[AttendanceDay | None, str]:
    """Return the row a new punch should fill, and check_in, check_out, or done."""
    today_row = (
        db.query(AttendanceDay)
        .filter(AttendanceDay.employee_id == employee_id, AttendanceDay.local_date == today.isoformat())
        .one_or_none()
    )
    if today_row is not None and today_row.check_in_at is not None and today_row.check_out_at is None:
        return today_row, "check_out"
    if today_row is not None and today_row.check_in_at is not None and today_row.check_out_at is not None:
        return today_row, "done"
    yesterday = (today - timedelta(days=1)).isoformat()
    previous = (
        db.query(AttendanceDay)
        .filter(AttendanceDay.employee_id == employee_id, AttendanceDay.local_date == yesterday)
        .one_or_none()
    )
    if previous is not None and previous.check_in_at is not None and previous.check_out_at is None:
        return previous, "check_out"
    return None, "check_in"


def leave_types(db: Session, start: date, end: date) -> dict[tuple[int, str], str]:
    rows = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.status == "approved",
            LeaveRequest.end_date >= start.isoformat(),
            LeaveRequest.start_date <= end.isoformat(),
        )
        .all()
    )
    found: dict[tuple[int, str], str] = {}
    for row in rows:
        first = max(date.fromisoformat(row.start_date), start)
        last = min(date.fromisoformat(row.end_date), end)
        for day in date_range(first, last):
            found[(row.employee_id, day.isoformat())] = row.type
    return found


def holiday_names(db: Session, start: date, end: date) -> dict[str, str]:
    rows = (
        db.query(Holiday)
        .filter(Holiday.local_date >= start.isoformat(), Holiday.local_date <= end.isoformat())
        .all()
    )
    return {row.local_date: row.name for row in rows}


def iso(value) -> str | None:
    local = as_local(value)
    if local is None:
        return None
    return local.isoformat()


def view_for(
    *,
    employee: Employee | None,
    row: AttendanceDay | None,
    day: date,
    office: OfficeSettings,
    holiday_name: str | None,
    leave_type: str | None,
    now,
    has_sample: bool,
) -> dict | None:
    check_in = row.check_in_at if row is not None else None
    check_out = row.check_out_at if row is not None else None
    has_punch = check_in is not None or check_out is not None
    created = as_local(employee.created_at) if employee is not None else None
    if employee is not None and not has_punch and created is not None:
        if day < created.date():
            return None
        if day == created.date() and created >= at_clock(day, office.work_end):
            return None
    result = classify(
        day=day,
        check_in=check_in,
        check_out=check_out,
        work_start=office.work_start,
        work_end=office.work_end,
        grace_minutes=office.grace_minutes,
        weekend_days=office.weekend_days,
        holiday=bool(holiday_name),
        on_leave=bool(leave_type),
        now=now,
    )
    if result["status"] == "off":
        return None
    if employee is not None and not has_punch and not employee.is_matchable(has_sample):
        return None
    name = employee.name if employee is not None else (row.employee_name if row is not None else "")
    department = ""
    if employee is not None and employee.department is not None:
        department = employee.department.name
    detail = holiday_name or leave_type or ""
    return {
        "id": row.id if row is not None else None,
        "employee_id": employee.id if employee is not None else (row.employee_id if row is not None else None),
        "employee_name": name,
        "department": department,
        "local_date": day.isoformat(),
        "check_in_at": iso(check_in),
        "check_out_at": iso(check_out),
        "check_in_manual": bool(row.check_in_manual) if row is not None else False,
        "check_out_manual": bool(row.check_out_manual) if row is not None else False,
        "has_check_in_snapshot": bool(row.check_in_snapshot) if row is not None else False,
        "has_check_out_snapshot": bool(row.check_out_snapshot) if row is not None else False,
        "late_minutes": result["late_minutes"],
        "early_minutes": result["early_minutes"],
        "worked_minutes": result["worked_minutes"],
        "status": result["status"],
        "note": row.note if row is not None else "",
        "detail": detail,
    }


def build_days(
    db: Session,
    start: date,
    end: date,
    *,
    employee_id: int | None = None,
    department_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    if end < start:
        return []
    office = get_office(db)
    enrolled = sample_ids(db)
    holidays = holiday_names(db, start, end)
    leaves = leave_types(db, start, end)
    employees = db.query(Employee).options(joinedload(Employee.user), joinedload(Employee.department)).all()
    if employee_id is not None:
        employees = [employee for employee in employees if employee.id == employee_id]
    if department_id is not None:
        employees = [employee for employee in employees if employee.department_id == department_id]
    punches = (
        db.query(AttendanceDay)
        .filter(AttendanceDay.local_date >= start.isoformat(), AttendanceDay.local_date <= end.isoformat())
        .all()
    )
    if employee_id is not None:
        punches = [row for row in punches if row.employee_id == employee_id]
    if department_id is not None:
        allowed = {employee.id for employee in employees}
        punches = [row for row in punches if row.employee_id in allowed]
    punch_map = {(row.employee_id, row.local_date): row for row in punches}
    now = local_now()
    views: list[dict] = []
    known_ids = {employee.id for employee in employees}
    for day in date_range(start, end):
        key = day.isoformat()
        for employee in employees:
            row = punch_map.get((employee.id, key))
            view = view_for(
                employee=employee,
                row=row,
                day=day,
                office=office,
                holiday_name=holidays.get(key),
                leave_type=leaves.get((employee.id, key)),
                now=now,
                has_sample=employee.id in enrolled,
            )
            if view is not None:
                views.append(view)
        if department_id is None:
            for row in punches:
                if row.local_date != key or row.employee_id in known_ids:
                    continue
                view = view_for(
                    employee=None,
                    row=row,
                    day=day,
                    office=office,
                    holiday_name=holidays.get(key),
                    leave_type=None,
                    now=now,
                    has_sample=False,
                )
                if view is not None:
                    views.append(view)
    if status:
        views = [view for view in views if view["status"] == status]
    views.sort(key=lambda view: view["employee_name"].lower())
    views.sort(key=lambda view: view["local_date"], reverse=True)
    return views


def persist_status(db: Session, row: AttendanceDay) -> None:
    office = get_office(db)
    day = date.fromisoformat(row.local_date)
    holiday = db.query(Holiday).filter(Holiday.local_date == row.local_date).first() is not None
    on_leave = False
    if row.employee_id is not None:
        on_leave = (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id == row.employee_id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= row.local_date,
                LeaveRequest.end_date >= row.local_date,
            )
            .first()
            is not None
        )
    result = classify(
        day=day,
        check_in=row.check_in_at,
        check_out=row.check_out_at,
        work_start=office.work_start,
        work_end=office.work_end,
        grace_minutes=office.grace_minutes,
        weekend_days=office.weekend_days,
        holiday=holiday,
        on_leave=on_leave,
        now=local_now(),
    )
    row.status = result["status"]
    row.late_minutes = result["late_minutes"]
    row.early_minutes = result["early_minutes"]
    row.worked_minutes = result["worked_minutes"]


def month_rows(days: list[dict], employees: list[Employee]) -> list[dict]:
    grouped: dict[int, dict] = {}
    for employee in employees:
        grouped[employee.id] = {
            "employee_id": employee.id,
            "employee_name": employee.name,
            "department": employee.department.name if employee.department is not None else "",
            "present": 0,
            "late": 0,
            "incomplete": 0,
            "absent": 0,
            "leave": 0,
            "late_minutes": 0,
        }
    for view in days:
        employee_id = view["employee_id"]
        if employee_id is None:
            continue
        bucket = grouped.get(employee_id)
        if bucket is None:
            bucket = {
                "employee_id": employee_id,
                "employee_name": view["employee_name"],
                "department": view["department"],
                "present": 0,
                "late": 0,
                "incomplete": 0,
                "absent": 0,
                "leave": 0,
                "late_minutes": 0,
            }
            grouped[employee_id] = bucket
        status = view["status"]
        if status in {"present", "left_early"}:
            bucket["present"] += 1
        elif status == "incomplete":
            bucket["incomplete"] += 1
        elif status == "absent":
            bucket["absent"] += 1
        elif status == "on_leave":
            bucket["leave"] += 1
        if status == "late" or (status == "incomplete" and view["late_minutes"] > 0):
            bucket["late"] += 1
        bucket["late_minutes"] += view["late_minutes"]
    rows = list(grouped.values())
    rows.sort(key=lambda row: row["employee_name"].lower())
    return rows
