"""Request bodies."""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    username: str
    password: str


class EmployeeUpdate(BaseModel):
    name: str | None = None
    employee_code: str | None = None
    department_id: int | None = None
    position: str | None = None
    status: str | None = None


class AccountCreate(BaseModel):
    username: str
    password: str


class LeaveCreate(BaseModel):
    type: str
    start_date: str
    end_date: str
    note: str = ""


class HolidayCreate(BaseModel):
    local_date: str
    name: str


class OfficeUpdate(BaseModel):
    work_start: str
    work_end: str
    grace_minutes: int
    weekend_days: list[str]


class DepartmentCreate(BaseModel):
    name: str


class Correction(BaseModel):
    employee_id: int
    local_date: str
    check_in: str | None = None
    check_out: str | None = None
    note: str


class CorrectionRequestCreate(BaseModel):
    local_date: str
    check_in: str | None = None
    check_out: str | None = None
    note: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PasswordSet(BaseModel):
    password: str


class UndoRequest(BaseModel):
    undo_token: str
