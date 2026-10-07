"""CSV cells stay quoted when a name contains a comma."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.app.csvout import attendance_table, clock_text, month_table, write_csv
from backend.app.workday import zone


class CsvTests(unittest.TestCase):
    def test_quotes_commas_and_writes_a_bom(self):
        text = write_csv(["Name"], [['Dara, "A"']])
        self.assertTrue(text.startswith("\ufeff"))
        self.assertIn('"Dara, ""A"""', text)

    def test_clock_uses_the_office_zone(self):
        local = datetime(2026, 10, 6, 8, 5, tzinfo=zone())
        utc = local.astimezone(ZoneInfo("UTC"))
        self.assertEqual(clock_text(utc.isoformat()), "08:05")

    def test_attendance_and_month_columns(self):
        headers, rows = attendance_table(
            [
                {
                    "local_date": "2026-10-06",
                    "employee_name": "Dara",
                    "department": "Shop",
                    "check_in_at": None,
                    "check_out_at": None,
                    "status": "absent",
                    "late_minutes": 0,
                    "early_minutes": 0,
                    "worked_minutes": 0,
                    "note": "",
                }
            ]
        )
        self.assertEqual(headers[0], "Date")
        self.assertEqual(rows[0][5], "Absent")
        month_headers, month_rows = month_table(
            [
                {
                    "employee_name": "Dara",
                    "department": "Shop",
                    "present": 1,
                    "late": 0,
                    "incomplete": 0,
                    "absent": 2,
                    "leave": 0,
                    "late_minutes": 0,
                }
            ]
        )
        self.assertEqual(month_headers[4], "Incomplete")
        self.assertEqual(month_rows[0][5], 2)


if __name__ == "__main__":
    unittest.main()
