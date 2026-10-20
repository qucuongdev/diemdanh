import os

os.environ["ATTENDANCE_TESTING"] = "1"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest
from core.supabase_service import SupabaseService, ServiceError
from core.config import BACKEND_VERSION
from httpx import ConnectError


class ServiceTests(unittest.TestCase):
    def test_client_initializes_with_public_key_without_network(self):
        service = object.__new__(SupabaseService)
        with (
            patch("core.supabase_service.SUPABASE_URL", "https://offline-example.supabase.co"),
            patch("core.supabase_service.SUPABASE_KEY", "sb_publishable_offline_test"),
            patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")),
        ):
            service.init_client()
        self.assertTrue(service.is_configured())
        self.assertEqual(service.client.options.postgrest_client_timeout, 15)
        self.assertEqual(service.client.options.storage_client_timeout, 20)

    def test_secret_key_is_rejected_before_client_creation(self):
        service = object.__new__(SupabaseService)
        with (
            patch("core.supabase_service.SUPABASE_URL", "https://offline-example.supabase.co"),
            patch("core.supabase_service.SUPABASE_KEY", "sb_secret_offline_test"),
            patch("core.supabase_service.create_client") as factory,
        ):
            service.init_client()
        self.assertFalse(service.is_configured())
        factory.assert_not_called()

    def setUp(self):
        self.service = object.__new__(SupabaseService)
        self.service.client = MagicMock()
        self.service.configuration_error = "Chưa cấu hình Supabase."
        self.service.current_profile = {"id": "u", "role": "admin", "is_active": True}
        self.service.current_user = SimpleNamespace(id="u")
        self.service._cache = {"branches": None, "staffs": None, "shifts": None}
        self.query = self.service.client.table.return_value
        for method in ("select", "eq", "gte", "lt", "lte", "order", "range", "update", "delete"):
            getattr(self.query, method).return_value = self.query
        self.query.execute.return_value = SimpleNamespace(data=[])

    def test_backend_failures_are_distinguished_without_exposing_server_details(self):
        class RpcError(Exception):
            def __init__(self, code):
                self.code = code
                super().__init__("token=DO_NOT_DISPLAY")

        for failure, expected in [
            (RpcError("PGRST202"), "backend_missing"),
            (RpcError("42883"), "backend_missing"),
            (RpcError("42501"), "backend_permission"),
            (ConnectError("token=DO_NOT_DISPLAY"), "backend_network"),
            (RuntimeError("token=DO_NOT_DISPLAY"), "backend_check_failed"),
        ]:
            with self.subTest(expected=expected):
                self.service.client.rpc.return_value.execute.side_effect = failure
                result = self.service.check_backend()
                self.assertFalse(result["success"])
                self.assertEqual(result["code"], expected)
                self.assertNotIn("DO_NOT_DISPLAY", result["message"])

    def test_only_exact_supported_backend_version_is_accepted(self):
        for version in [None, True, 2, "3", [3], BACKEND_VERSION + 1, BACKEND_VERSION]:
            with self.subTest(version=version):
                self.service.client.rpc.return_value.execute.return_value = SimpleNamespace(data=version)
                result = self.service.check_backend()
                self.assertEqual(result["success"], type(version) is int and version == BACKEND_VERSION)

    def test_failed_backend_check_clears_authenticated_session(self):
        self.service.client.auth.sign_in_with_password.return_value = SimpleNamespace(user=SimpleNamespace(id="u"))
        self.service.client.rpc.return_value.execute.return_value = SimpleNamespace(data=2)
        with patch.object(self.service, "get_profile", return_value={
            "success": True, "profile": self.service.current_profile,
        }):
            result = self.service.login("offline@example.com", "test-password")
        self.assertEqual(result["code"], "backend_incompatible")
        self.service.client.auth.sign_out.assert_called_once()
        self.assertIsNone(self.service.current_profile)
        self.assertIsNone(self.service.current_user)

    def test_missing_configuration_is_reported_before_any_authentication(self):
        self.service.client = None
        result = self.service.login("offline@example.com", "test-password")
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], self.service.configuration_error)

    def test_history_queries_branch_and_exclusive_local_day_on_server(self):
        self.service.get_attendance_history("b", "u", "2026-10-20", 51, 50)
        self.query.eq.assert_any_call("branch_id", "b")
        self.query.eq.assert_any_call("user_id", "u")
        self.query.gte.assert_called_once_with("check_in", "2026-10-20T00:00:00+07:00")
        self.query.lt.assert_called_once_with("check_in", "2026-10-21T00:00:00+07:00")
        self.query.range.assert_called_once_with(50, 100)

    def test_read_error_is_not_an_empty_success(self):
        self.query.execute.side_effect = RuntimeError("secret server error")
        with self.assertRaises(ServiceError):
            self.service.get_attendance_history()

    def test_complete_reports_read_every_page_including_server_caps(self):
        self.query.execute.side_effect = [
            SimpleNamespace(data=[{"id": str(i)} for i in range(3)]),
            SimpleNamespace(data=[{"id": "3"}]),
            SimpleNamespace(data=[]),
        ]
        records = self.service.get_monthly_attendance_data("b", 2026, 10)
        self.assertEqual(len(records), 4)
        self.assertEqual([call.args[0] for call in self.query.range.call_args_list], [0, 3, 4])

    def test_missing_admin_rpc_has_no_profile_fallback(self):
        self.service.client.rpc.return_value.execute.side_effect = RuntimeError("PGRST202 rpc_update_user")
        result = self.service.update_user_full("v", "Test", "staff", "b", "")
        self.assertFalse(result["success"])
        self.service.client.table.assert_not_called()

    def test_non_admin_cannot_mutate_admin_resources(self):
        self.service.current_profile = {"id": "u", "role": "staff", "branch_id": "b", "is_active": True}
        self.assertFalse(self.service.delete_user_full("v")["success"])
        self.assertFalse(self.service.register_device("b", "uuid", "Test")["success"])
        self.service.client.table.assert_not_called()
        self.service.client.rpc.assert_not_called()

    def test_reviews_are_conditional_and_reject_spoofed_reviewer(self):
        self.assertFalse(self.service.review_leave_request("r", "approved", "other")["success"])
        self.service.client.table.assert_not_called()
        result = self.service.review_leave_request("r", "approved", "u")
        self.query.eq.assert_any_call("status", "pending")
        self.assertFalse(result["success"])

    def test_logout_clears_all_cached_metadata(self):
        self.service._cache = {"staffs": ["previous session"]}
        self.service.logout()
        self.assertIsNone(self.service.current_profile)
        self.assertTrue(all(value is None for value in self.service._cache.values()))

    def test_device_metadata_is_not_silently_truncated(self):
        self.query.execute.side_effect = [SimpleNamespace(data=[{"id": "d"}]), SimpleNamespace(data=[])]
        self.assertEqual(self.service.get_allowed_devices(), [{"id": "d"}])

    def test_private_proof_url_rejects_external_hosts_and_traversal(self):
        for path in ("https://evil.example/attendance_proofs/u/x.jpg", "u/../x.jpg"):
            with self.assertRaises(ServiceError):
                self.service.get_proof_url(path)
        self.service.client.storage.from_.assert_not_called()

    def test_upload_requires_note_branch_and_self(self):
        result = self.service.upload_compressed_proof("missing.jpg", "someone", "b", "test")
        self.assertFalse(result["success"])
        self.service.client.storage.from_.assert_not_called()
