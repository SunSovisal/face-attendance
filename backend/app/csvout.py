"""Spreadsheet downloads."""
import csv
import io
from datetime import datetime

from fastapi.responses import Response

from backend.app.workday import as_local

STATUS_LABELS = {
    "present": "Present",
    "late": "Late",
    "left_early": "Left early",
    "incomplete": "Incomplete",
    "absent": "Absent",
    "on_leave": "On leave",
    "holiday": "Holiday",
    "due": "Not in yet",
}


def clock_text(value: str | None) -> str:
    if not value:
        return ""
    local = as_local(datetime.fromisoformat(value))
    if local is None:
        return ""
    return local.strftime("%H:%M")


def status_label(value: str) -> str:
    return STATUS_LABELS.get(value, value)


def write_csv(headers: list[str], rows: list[list[object]]) -> str:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> Response:
    return Response(
        content=write_csv(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def attendance_table(days: list[dict]) -> tuple[list[str], list[list[object]]]:
    headers = [
        "Date",
        "Employee",
        "Department",
        "Check in",
        "Check out",
        "Status",
        "Late minutes",
        "Early minutes",
        "Worked minutes",
        "Note",
    ]
    rows = [
        [
            day["local_date"],
            day["employee_name"],
            day["department"],
            clock_text(day["check_in_at"]),
            clock_text(day["check_out_at"]),
            status_label(day["status"]),
            day["late_minutes"],
            day["early_minutes"],
            day["worked_minutes"],
            day["note"],
        ]
        for day in days
    ]
    return headers, rows


def month_table(rows_in: list[dict]) -> tuple[list[str], list[list[object]]]:
    headers = ["Employee", "Department", "Present", "Late", "Incomplete", "Absent", "Leave", "Late minutes"]
    rows = [
        [
            row["employee_name"],
            row["department"],
            row["present"],
            row["late"],
            row["incomplete"],
            row["absent"],
            row["leave"],
            row["late_minutes"],
        ]
        for row in rows_in
    ]
    return headers, rows
