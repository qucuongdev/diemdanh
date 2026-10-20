import unittest
from core.domain import display_time, first_attendance, validate_profile, safe_excel_text
from core.security import validate_public_key
from core.reports import summarize, export_attendance
from pathlib import Path
import tempfile
import openpyxl


class DomainTests(unittest.TestCase):
    def test_timestamps_convert_to_vietnam_time_and_accept_null(self):
        self.assertEqual(display_time("2026-10-20T01:00:00Z"), "08:00:00")
        self.assertEqual(display_time("2026-10-20T08:00:00+07:00"), "08:00:00")
        self.assertEqual(display_time(None), "—")
        self.assertEqual(display_time("bad input"), "—")

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
