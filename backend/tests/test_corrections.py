"""Correction requests and password changes against a temporary database."""
import unittest
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.correct import apply_correction
from backend.app.db import Base
from backend.app.models import CorrectionRequest, Employee, OfficeSettings, User
from backend.app.routes.auth import change_password
from backend.app.routes.corrections import request_correction, review
from backend.app.schemas import CorrectionRequestCreate, PasswordChange
from backend.app.security import hash_password, verify_password
from backend.app.workday import local_now


def memory_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_fk(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.db = memory_session()
        self.db.add(OfficeSettings(id=1, work_start="08:00", work_end="17:00", grace_minutes=10, weekend_days="sat,sun"))
        self.employee_user = User(username="dara", password_hash=hash_password("secret-12"), role="employee", status="active")
        self.admin = User(username="boss", password_hash=hash_password("secret-12"), role="admin", status="active")
        self.db.add(self.employee_user)
        self.db.add(self.admin)
        self.db.flush()
        self.employee = Employee(user_id=self.employee_user.id, name="Dara", status="active")
        self.db.add(self.employee)
        self.db.commit()
        self.db.refresh(self.employee_user)
        self.day = (local_now().date() - timedelta(days=1)).isoformat()

    def tearDown(self):
        self.db.close()

    def test_apply_marks_a_late_manual_day(self):
        row = apply_correction(self.db, self.employee, local_now().date() - timedelta(days=1), "09:00", "17:00", "Forgot the camera", self.admin.id)
        self.assertTrue(row.check_in_manual)
        self.assertTrue(row.check_out_manual)
        self.assertEqual(row.status, "late")
        self.assertEqual(row.late_minutes, 60)
        self.assertEqual(row.note, "Forgot the camera")

    def test_request_then_approve_writes_the_day(self):
        created = request_correction(
            CorrectionRequestCreate(local_date=self.day, check_in="09:00", check_out="17:00", note="Missed the desk"),
            self.db,
            self.employee_user,
        )
        self.assertEqual(created["status"], "pending")
        with self.assertRaises(HTTPException) as duplicate:
            request_correction(
                CorrectionRequestCreate(local_date=self.day, check_in="09:10", check_out=None, note="Again"),
                self.db,
                self.employee_user,
            )
        self.assertEqual(duplicate.exception.status_code, 409)
        approved = review(created["id"], "approved", self.db, self.admin)
        self.assertEqual(approved["status"], "approved")
        saved = self.db.query(CorrectionRequest).one()
        self.assertEqual(saved.status, "approved")
        from backend.app.models import AttendanceDay

        day = self.db.query(AttendanceDay).one()
        self.assertEqual(day.note, "Missed the desk")
        self.assertTrue(day.check_in_manual)

    def test_future_day_is_refused(self):
        tomorrow = (local_now().date() + timedelta(days=1)).isoformat()
        with self.assertRaises(HTTPException) as rejected:
            request_correction(
                CorrectionRequestCreate(local_date=tomorrow, check_in="09:00", check_out=None, note="Too soon"),
                self.db,
                self.employee_user,
            )
        self.assertEqual(rejected.exception.status_code, 400)

    def test_reject_leaves_the_workday_alone(self):
        created = request_correction(
            CorrectionRequestCreate(local_date=self.day, check_in="09:00", check_out=None, note="Traffic"),
            self.db,
            self.employee_user,
        )
        review(created["id"], "rejected", self.db, self.admin)
        from backend.app.models import AttendanceDay

        self.assertEqual(self.db.query(AttendanceDay).count(), 0)


class PasswordTests(unittest.TestCase):
    def setUp(self):
        self.db = memory_session()
        self.user = User(username="dara", password_hash=hash_password("old-password"), role="employee", status="active")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_change_requires_the_current_password(self):
        with self.assertRaises(HTTPException):
            change_password(PasswordChange(current_password="nope-nope", new_password="new-password"), self.db, self.user)
        change_password(PasswordChange(current_password="old-password", new_password="new-password"), self.db, self.user)
        self.assertTrue(verify_password("new-password", self.user.password_hash))
        with self.assertRaises(HTTPException):
            change_password(PasswordChange(current_password="new-password", new_password="new-password"), self.db, self.user)


if __name__ == "__main__":
    unittest.main()
