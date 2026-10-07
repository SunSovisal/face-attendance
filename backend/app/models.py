"""Users, employees, workdays, leave, and office settings."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="employee")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    employee: Mapped["Employee | None"] = relationship(back_populates="user", uselist=False)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    employees: Mapped[list["Employee"]] = relationship(back_populates="department")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    employee_code: Mapped[str | None] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User | None] = relationship(back_populates="employee")
    department: Mapped[Department | None] = relationship(back_populates="employees")
    samples: Mapped[list["FaceSample"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )

    def is_matchable(self, has_sample: bool) -> bool:
        if self.status != "active" or not has_sample:
            return False
        account = self.user
        return account is None or account.status == "active"


class FaceSample(Base):
    __tablename__ = "face_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    image_path: Mapped[str] = mapped_column(String(500))
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    employee: Mapped[Employee] = relationship(back_populates="samples")


class AttendanceDay(Base):
    __tablename__ = "attendance_days"
    __table_args__ = (UniqueConstraint("employee_id", "local_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    employee_name: Mapped[str] = mapped_column(String(120))
    local_date: Mapped[str] = mapped_column(String(10), index=True)
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_in_distance: Mapped[float | None] = mapped_column(Float)
    check_in_snapshot: Mapped[str | None] = mapped_column(String(500))
    check_in_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    check_in_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out_distance: Mapped[float | None] = mapped_column(Float)
    check_out_snapshot: Mapped[str | None] = mapped_column(String(500))
    check_out_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    check_out_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="incomplete")
    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    early_minutes: Mapped[int] = mapped_column(Integer, default=0)
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(500), default="")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[str] = mapped_column(String(10))
    end_date: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    employee: Mapped[Employee] = relationship()


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(primary_key=True)
    local_date: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))


class CorrectionRequest(Base):
    __tablename__ = "correction_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    local_date: Mapped[str] = mapped_column(String(10))
    check_in: Mapped[str | None] = mapped_column(String(5))
    check_out: Mapped[str | None] = mapped_column(String(5))
    note: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    employee: Mapped[Employee] = relationship()


class OfficeSettings(Base):
    __tablename__ = "office_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_start: Mapped[str] = mapped_column(String(5), default="08:00")
    work_end: Mapped[str] = mapped_column(String(5), default="17:00")
    grace_minutes: Mapped[int] = mapped_column(Integer, default=10)
    weekend_days: Mapped[str] = mapped_column(String(40), default="sat,sun")
