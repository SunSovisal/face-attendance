"""Workday status rules."""
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.app.config import settings
from backend.app.workday import classify, validate_office

ZONE = ZoneInfo(settings.app_timezone)
DAY = date(2026, 10, 5)


def at(hour: int, minute: int, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZONE)


def status(**overrides) -> dict:
    values = {
        "day": DAY,
        "check_in": None,
        "check_out": None,
        "work_start": "08:00",
        "work_end": "17:00",
        "grace_minutes": 10,
        "weekend_days": "sat,sun",
        "holiday": False,
        "on_leave": False,
        "now": at(18, 0),
    }
    values.update(overrides)
    return classify(**values)


class WorkdayTests(unittest.TestCase):
    def test_present_inside_grace(self):
        result = status(check_in=at(8, 10), check_out=at(17, 0))
        self.assertEqual(result["status"], "present")
        self.assertEqual(result["late_minutes"], 0)
        self.assertEqual(result["worked_minutes"], 530)

    def test_late_counts_from_the_start(self):
        result = status(check_in=at(8, 11), check_out=at(17, 0))
        self.assertEqual(result["status"], "late")
        self.assertEqual(result["late_minutes"], 11)

    def test_left_early(self):
        result = status(check_in=at(8, 0), check_out=at(16, 50))
        self.assertEqual(result["status"], "left_early")
        self.assertEqual(result["early_minutes"], 10)

    def test_late_and_left_early_keep_both_counts(self):
        result = status(check_in=at(8, 11), check_out=at(16, 50))
        self.assertEqual(result["status"], "late")
        self.assertEqual(result["late_minutes"], 11)
        self.assertEqual(result["early_minutes"], 10)

    def test_incomplete_when_still_in(self):
        self.assertEqual(status(check_in=at(8, 0))["status"], "incomplete")

    def test_absent_after_the_day_ends(self):
        self.assertEqual(status()["status"], "absent")

    def test_due_before_the_day_ends(self):
        self.assertEqual(status(now=at(9, 0))["status"], "due")

    def test_weekend_is_off(self):
        self.assertEqual(status(day=date(2026, 10, 3))["status"], "off")

    def test_holiday_and_leave_win(self):
        self.assertEqual(status(holiday=True)["status"], "holiday")
        self.assertEqual(status(on_leave=True)["status"], "on_leave")
        punched = status(holiday=True, check_in=at(9, 0), check_out=at(17, 0))
        self.assertEqual(punched["status"], "holiday")
        self.assertEqual(punched["late_minutes"], 60)

    def test_office_hours_need_a_real_day(self):
        self.assertIsNone(validate_office("08:00", "17:00", 10, ["sat", "sun"]))
        self.assertIsNotNone(validate_office("17:00", "08:00", 10, []))
        self.assertIsNotNone(validate_office("08:00", "17:00", 10, ["fun"]))


if __name__ == "__main__":
    unittest.main()
