"""Regression tests: internal diagnostics must never become public UI messages."""

import os
os.environ["ATTENDANCE_TESTING"] = "1"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from core.supabase_service import SupabaseService
from core.ui_messages import (
    SYSTEM_UNAVAILABLE, CONNECTION_UNAVAILABLE, UserInputError, public_mutation_result,
    public_error_message, public_payroll_warning,
)
from core.domain import validate_profile
from core.personnel import validate_terms


class PublicMessageTests(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(SupabaseService)
        self.service.client = MagicMock()
        self.service.current_profile = {"id": "u", "role": "admin", "is_active": True}
        self.service._cache = {"staffs": None}

    def assert_public(self, message):
        for forbidden in ["backend", "supabase", "migration", "rpc", "postgrest", ".env", "supabase_key",
                          "pgrst", "42501", "traceback", "select ", "do_not_display", "http://", "https://"]:
            self.assertNotIn(forbidden, message.lower())

    def test_backend_mismatch_and_system_failures_expose_no_implementation_details(self):
        for version in [None, True, 0, 3, "4", {"error": "DO_NOT_DISPLAY"}]:
            self.service.client.rpc.return_value.execute.return_value = SimpleNamespace(data=version)
            result = self.service.check_backend()
            self.assertFalse(result["success"])
            self.assertEqual(result["message"], SYSTEM_UNAVAILABLE)
            self.assert_public(result["message"])
        for code in ["PGRST202", "42883", "42501", "PGRST301", "unexpected"]:
            error = RuntimeError("SELECT password DO_NOT_DISPLAY")
            error.code = code
            self.service.client.rpc.return_value.execute.side_effect = error
            result = self.service.check_backend()
            self.assertEqual(result["message"], SYSTEM_UNAVAILABLE)
            self.assert_public(result["message"])
        self.service.client.rpc.return_value.execute.side_effect = ConnectionError("DO_NOT_DISPLAY")
        self.assertEqual(self.service.check_backend()["message"], CONNECTION_UNAVAILABLE)

    def test_invalid_configuration_is_generic_and_never_contacts_the_server(self):
        for key in ["", "sb_secret_DO_NOT_DISPLAY"]:
            with patch("core.supabase_service.SUPABASE_URL", "https://offline.invalid"), \
                 patch("core.supabase_service.SUPABASE_KEY", key), \
                 patch("core.supabase_service.create_client") as factory:
                self.service.init_client()
            factory.assert_not_called()
            self.assertEqual(self.service.configuration_error, SYSTEM_UNAVAILABLE)
            self.assert_public(self.service.configuration_error)

    def test_rpc_message_text_is_discarded_even_when_marked_successful(self):
        for success in [False, True]:
            response = {"success": success, "message": "PGRST202 RPC DO_NOT_DISPLAY", "attendance_id": "a"}
            for method, args in [
                (self.service.check_in, ("s", "device")),
                (self.service.check_out, ("a", "device")),
                (self.service.create_user, ("fake@example.invalid", "fake-password", "Test", "staff", "b", "")),
                (self.service.update_user_full, ("u", "Test", "staff", "b", "", True)),
                (self.service.delete_user_full, ("u",)),
                (self.service.save_employee_private, ("u", {}, 0)),
                (self.service.save_pay_terms, ("u", "2026-10-01", {}, 0)),
            ]:
                self.service.client.rpc.return_value.execute.return_value = SimpleNamespace(data=response)
                result = method(*args)
                self.assertEqual(result["success"], success)
                self.assert_public(result["message"])

    def test_personnel_transport_and_validation_error_messages_are_not_forwarded(self):
        for raw in ["RPC migration 05 SELECT DO_NOT_DISPLAY", "PERSONNEL_STALE query=DO_NOT_DISPLAY"]:
            self.service.client.rpc.return_value.execute.side_effect = RuntimeError(raw)
            result = self.service.get_employee_private("u")
            self.assertFalse(result["success"])
            self.assert_public(result["message"])

    def test_only_code_owned_validation_errors_can_be_shown_as_validation(self):
        with self.assertRaises(UserInputError):
            validate_profile({"id": "u", "role": "staff", "is_active": False})
        with self.assertRaises(UserInputError):
            validate_terms({})
        for malformed in [None, {}, [], "RPC DO_NOT_DISPLAY", {"success": "true"}]:
            self.assertEqual(public_mutation_result(malformed), {"success": False, "message": SYSTEM_UNAVAILABLE})

    def test_unknown_errors_are_blocked_at_the_final_display_boundary(self):
        for value in ["permission denied for table payroll_snapshots", "PGRST202 query=SELECT salary", None,
                      {"error": "secret"}, ValueError("DO_NOT_DISPLAY"),
                      UserInputError("RPC DO_NOT_DISPLAY"), "Lỗi mới chưa được duyệt"]:
            self.assertEqual(public_error_message(value), SYSTEM_UNAVAILABLE)
        self.assertEqual(public_error_message("Thiết bị chưa được cấp phép."), "Thiết bị chưa được cấp phép.")
        self.assertEqual(public_error_message(UserInputError("CCCD/CMND cần 9 hoặc 12 chữ số.")),
                         "CCCD/CMND cần 9 hoặc 12 chữ số.")

    def test_payroll_warnings_allow_only_known_business_text_and_valid_dates(self):
        for value in ["RPC permission denied", "2026-10-01: SELECT salary", "2026-02-30: Chưa check-out",
                      "Chưa check-out\nSQL DETAIL: secret", {"error": "secret"}]:
            self.assertEqual(public_payroll_warning(value), SYSTEM_UNAVAILABLE)
        self.assertEqual(public_payroll_warning("2026-10-01: Chưa check-out"), "2026-10-01: Chưa check-out")
        self.assertEqual(public_payroll_warning("Ca chồng nhau · Tổng ca vượt giờ chuẩn/ngày"),
                         "Ca chồng nhau · Tổng ca vượt giờ chuẩn/ngày")
        translated = public_payroll_warning("2026-10-01: Phút muộn không khớp timestamp")
        self.assertNotIn("timestamp", translated)
        self.assertIn("chưa khớp", translated)
