import unittest
from core.domain import display_time, display_duration, parse_timestamp, first_attendance, validate_profile, safe_excel_text
from core.domain import timestamp_tooltip
from core.security import validate_public_key
from core.reports import summarize, export_attendance
from pathlib import Path
import tempfile
import openpyxl
from datetime import timedelta


class DomainTests(unittest.TestCase):
    def test_timestamps_convert_to_vietnam_time_and_accept_null(self):
        self.assertEqual(display_time("2026-10-20T01:00:59Z"), "08:00")
        self.assertEqual(display_time("2026-10-20T08:00:00+07:00"), "08:00")
        self.assertEqual(display_time("2026-10-20T23:59:59Z"), "06:59")
        self.assertEqual(parse_timestamp("2026-10-20T01:00:59Z").second, 59)
        self.assertEqual(display_time(None), "—")
        self.assertEqual(display_time("bad input"), "—")

    def test_duration_is_hours_minutes_and_never_wraps_at_24_hours(self):
        for minutes, expected in [(0, "00:00"), (1, "00:01"), (59, "00:59"), (60, "01:00"),
                                  (369, "06:09"), (1501, "25:01"), (6000, "100:00")]:
            with self.subTest(minutes=minutes):
                self.assertEqual(display_duration(minutes), expected)
        for invalid in (None, -1, True, "369", 1.5):
            with self.subTest(invalid=invalid):
                self.assertEqual(display_duration(invalid), "—")

    def test_minute_display_retains_exact_second_and_local_date_in_tooltip(self):
        value = "2026-10-20T18:00:01Z"
        self.assertEqual(display_time(value), "01:00")
        self.assertEqual(timestamp_tooltip(value), "21/10/2026 01:00:01 · Giờ Việt Nam")
        self.assertEqual(timestamp_tooltip(None), "—")
        self.assertEqual(timestamp_tooltip("invalid"), "—")

    def test_report_sums_raw_minutes_before_display_conversion(self):
        record = {"user_id": "u", "attendance": {"is_late": True, "late_minutes": 65}}
        result = summarize([record, record])[0]
        self.assertEqual(result["late_minutes"], 130)
        self.assertEqual(display_duration(result["late_minutes"]), "02:10")

    def test_excel_durations_are_numeric_and_support_more_than_24_hours(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duration.xlsx"
            schedules = [{"attendance": {"check_in": "2026-10-20T01:08:59Z", "late_minutes": minutes}}
                         for minutes in (369, 1501, None)]
            export_attendance(path, schedules, "Test")
            workbook = openpyxl.load_workbook(path)
            sheet = workbook.active
            self.assertEqual(sheet["E2"].value, "Check-in")
            self.assertEqual(sheet["F2"].value, "Check-out")
            self.assertEqual(sheet["E3"].value, "08:08")
            self.assertEqual(sheet["G3"].value, timedelta(hours=6, minutes=9))
            self.assertEqual(sheet["G4"].value, timedelta(hours=25, minutes=1))
            self.assertEqual(sheet["G4"].number_format, "[h]:mm")
            self.assertIsNone(sheet["G5"].value)
            workbook.close()

    def test_attendance_relation_handles_dict_list_and_null(self):
        for value in (None, [], {}):
            self.assertEqual(first_attendance({"attendance": value}), {})
        for value in ({"id": "a"}, [{"id": "a"}]):
            self.assertEqual(first_attendance({"attendance": value}), {"id": "a"})

    def test_profiles_fail_closed(self):
        valid = {"id": "u", "role": "staff", "branch_id": "b", "is_active": True}
        self.assertEqual(validate_profile(valid), valid)
        for patch in ({"role": "owner"}, {"is_active": False}, {"is_active": None}, {"branch_id": None}):
            with self.assertRaises(ValueError):
                validate_profile({**valid, **patch})

    def test_server_keys_rejected(self):
        import base64
        import json

        validate_public_key("sb_publishable_test")
        for key in ("sb_secret_test", "anything"):
            with self.assertRaises(ValueError):
                validate_public_key(key)
        payload = base64.urlsafe_b64encode(json.dumps({"role": "service_role"}).encode()).decode().rstrip("=")
        with self.assertRaises(ValueError):
            validate_public_key(f"x.{payload}.x")
        for claims in ([], None, 1, "anon"):
            payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
            with self.assertRaises(ValueError):
                validate_public_key(f"x.{payload}.x")

    def test_report_does_not_count_unrecorded_or_leave_as_ontime(self):
        records = [
            {"profiles": {"id": "u", "full_name": "Test"}, "status": status, "attendance": attendance}
            for status, attendance in [
                ("scheduled", None),
                ("leave", None),
                ("completed", [{"is_late": False}]),
                ("completed", {"is_late": True, "late_minutes": 7}),
            ]
        ]
        result = summarize(records)[0]
        self.assertEqual(
            (result["total"], result["ontime"], result["late"], result["leave"], result["unrecorded"]),
            (4, 1, 1, 1, 1),
        )

    def test_excel_export_handles_null_and_does_not_execute_formulas(self):
        self.assertEqual(safe_excel_text(" =SUM(A1)"), "' =SUM(A1)")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.xlsx"
            export_attendance(
                path,
                [{"profiles": {"full_name": "=1+1"}, "attendance": {"check_in": None, "check_out": None}}],
                "Test",
            )
            workbook = openpyxl.load_workbook(path)
            self.assertEqual(workbook.active["B3"].data_type, "s")
            self.assertEqual(workbook.active["B3"].value, "'=1+1")
            workbook.close()
