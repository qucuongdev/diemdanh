"""Offline personnel validation, service security, Qt lifecycle and payroll exports."""

import os

os.environ["ATTENDANCE_TESTING"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""

from contextlib import ExitStack
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
import openpyxl
from PySide6.QtWidgets import QWidget, QMessageBox
from PySide6.QtCore import Qt
from core.personnel import display_money, validate_terms, validate_personal
from core.payroll_export import export_payroll
from core.supabase_service import SupabaseService
from core.qt_worker import QtWorker
from core.ui_messages import SYSTEM_UNAVAILABLE
from test_qt import APP, ADMIN, STAFF, fake_service, until, THEMES
from views_qt.personnel_dialog import EmployeeDialog
from views_qt.payroll_view import PayrollView, PayrollDetailDialog, BirthdayDialog
from views_qt.common import FormDialog, TableModel


def payroll_row(name="Nhân viên thử nghiệm"):
    return {"user_id": "staff", "month": "2026-09-01", "full_name": name,
            "employee": {"id": "staff", "full_name": name}, "monthly_salary": 9000000,
            "standard_minutes": 12480, "expected_minutes": 12480, "regular_minutes": 12465,
            "paid_leave_minutes": 0, "extra_minutes": 480, "missing_minutes": 15,
            "late_count": 1, "deduction": 10817, "extra_pay": 346154, "bonus": 500000,
            "base_salary": 9000000, "net_salary": 9835337, "finalized": False, "warnings": [],
            "source_signature": "offline-signature", "period_closed": True,
            "days": [{"date": "2026-09-01", "kind": "regular", "planned_minutes": 480,
                      "worked_minutes": 465, "late_minutes": 15, "note": "", "warning": "", "revision": 0}]}


class PersonnelValidationTests(unittest.TestCase):
    def test_money_and_terms_do_not_use_binary_float(self):
        self.assertEqual(display_money("999999999999"), "999.999.999.999 đ")
        self.assertEqual(display_money("346153.5"), "346.154 đ")
        self.assertEqual(display_money(None), "—")
        values = {"effective_month": "2026-09-01", "monthly_salary": "9000000", "paid_rest_days": "4",
                  "daily_minutes": "480", "attendance_bonus": "500000", "allowed_late_count": "2"}
        month, terms = validate_terms(values)
        self.assertEqual(month, "2026-09-01")
        self.assertEqual(terms["monthly_salary"], 9000000)
        self.assertEqual(validate_terms({**values, "daily_minutes": "08:00"})[1]["daily_minutes"], 480)
        self.assertEqual(validate_terms({**values, "daily_minutes": "59 phút"})[1]["daily_minutes"], 59)
        for key, invalid in [("effective_month", "2026-09-02"), ("monthly_salary", "NaN"),
                             ("monthly_salary", "Infinity"), ("monthly_salary", "-1"),
                             ("monthly_salary", "1.5"), ("daily_minutes", "0"),
                             ("daily_minutes", "1441"), ("paid_rest_days", "28"),
                             ("daily_minutes", "00:60"), ("daily_minutes", "24:01"),
                             ("attendance_bonus", "-1"), ("allowed_late_count", "-1")]:
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                validate_terms({**values, key: invalid})

    def test_personal_dates_and_leading_zero_identifiers(self):
        values = {"birth_date": "2000-02-29", "identity_number": "001234567890",
                  "bank_account": "0000123456", "birthday_notice_days": "7"}
        self.assertEqual(validate_personal(values, date(2026, 10, 21))["bank_account"], "0000123456")
        for patch_values in ({"birth_date": "2027-01-01"}, {"birth_date": "2001-02-29"},
                             {"identity_number": "abc"}, {"birthday_notice_days": "61"},
                             {"hire_date": "2026-10-21", "end_date": "2026-10-20"}):
            with self.subTest(patch_values=patch_values), self.assertRaises(ValueError):
                validate_personal({**values, **patch_values}, date(2026, 10, 21))

    def test_payroll_excel_preserves_numbers_durations_and_formula_safety(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "payroll.xlsx"
            export_payroll(path, [payroll_row("=1+1")], "2026-09-01")
            workbook = openpyxl.load_workbook(path)
            sheet = workbook.active
            self.assertEqual(sheet["A3"].data_type, "s")
            self.assertEqual(sheet["A3"].value, "'=1+1")
            self.assertEqual(sheet["C3"].value, 9000000)
            self.assertEqual(sheet["D3"].value, timedelta(minutes=12480))
            self.assertEqual(sheet["D3"].number_format, "[hh]:mm")
            self.assertEqual(sheet["H3"].number_format, '[m]" phút"')
            self.assertEqual(sheet["M3"].value, 9835337)
            self.assertEqual(sheet["N3"].value, "Tạm tính")
            workbook.close()
            path.write_bytes(b"original")
            with patch("core.payroll_export.os.replace", side_effect=PermissionError), self.assertRaises(PermissionError):
                export_payroll(path, [payroll_row()], "2026-09-01")
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(len(list(Path(folder).iterdir())), 1)


class PersonnelServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(SupabaseService)
        self.service.client = MagicMock()
        self.service.current_profile = ADMIN
        self.service.client.rpc.return_value.execute.return_value = SimpleNamespace(data={"success": True})

    def test_every_personnel_operation_rejects_nonadmins_before_network(self):
        methods = [("get_employee_private", ("u",)), ("save_employee_private", ("u", {}, 0)),
                   ("save_pay_terms", ("u", "2026-09-01", {}, 0)),
                   ("set_payroll_day", ("u", "2026-09-01", "rest", "note", 0)),
                   ("get_payroll_page", ("2026-09-01",)), ("get_payroll_preview", ("u", "2026-09-01")),
                   ("finalize_payroll", ("u", "2026-09-01", "signature")), ("get_upcoming_birthdays", ())]
        for profile in [STAFF, {**STAFF, "role": "storemanager"}, {**ADMIN, "is_active": False}, None]:
            self.service.current_profile = profile
            for method, args in methods:
                with self.subTest(profile=profile, method=method):
                    self.assertFalse(getattr(self.service, method)(*args)["success"])
        self.service.client.rpc.assert_not_called()

    def test_scope_pagination_and_signature_are_sent_to_the_rpc(self):
        self.service.get_payroll_page("2026-09-01", 40, 21, "name", "branch")
        self.service.client.rpc.assert_called_with("rpc_payroll_page", {
            "p_month": "2026-09-01", "p_offset": 40, "p_limit": 21, "p_search": "name", "p_branch_id": "branch"})
        self.service.finalize_payroll("u", "2026-09-01", "source-sig")
        self.service.client.rpc.assert_called_with("rpc_finalize_payroll", {
            "p_user_id": "u", "p_month": "2026-09-01", "p_signature": "source-sig"})
        self.service.client.table.assert_not_called()

    def test_raw_errors_and_invalid_responses_never_leak_or_succeed(self):
        for error in [RuntimeError("private-id=123 token=DO_NOT_SHOW"),
                      RuntimeError("PERSONNEL_STALE private-id=123")]:
            self.service.client.rpc.side_effect = error
            result = self.service.get_employee_private("u")
            self.assertFalse(result["success"])
            self.assertNotIn("123", result["message"])
            self.assertNotIn("DO_NOT_SHOW", result["message"])
        self.service.client.rpc.side_effect = None
        self.service.client.rpc.return_value.execute.return_value = SimpleNamespace(data=None)
        self.assertFalse(self.service.get_employee_private("u")["success"])
        self.service.client.rpc.return_value.execute.return_value = SimpleNamespace(data={"unexpected": "shape"})
        self.assertFalse(self.service.get_payroll_page("2026-09-01")["success"])
        self.assertFalse(self.service.get_payroll_preview("u", "2026-09-01")["success"])


class PersonnelQtTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.service = fake_service()
        self.service.get_employee_private.return_value = {"success": True, "data": {"details": None, "terms": []}}
        self.service.get_payroll_page.return_value = {"success": True, "data": [payroll_row()]}
        self.service.get_payroll_preview.return_value = {"success": True, "data": payroll_row()}
        for target in ["core.supabase_service.SupabaseService", "views_qt.personnel_dialog.SupabaseService",
                       "views_qt.payroll_view.SupabaseService"]:
            self.stack.enter_context(patch(target, return_value=self.service))
        self.parent = QWidget()
        self.parent.show()
        self.windows = []

    def tearDown(self):
        until(lambda: not QtWorker.busy())
        for window in self.windows:
            window.close()
        self.parent.close()
        self.parent.deleteLater()
        APP.processEvents()
        self.stack.close()
        APP.theme_manager.set_mode("dark")

    def view(self):
        view = PayrollView(self.parent, ADMIN)
        self.windows.append(view)
        until(lambda: not QtWorker.busy())
        return view

    def test_payroll_is_paginated_and_failures_clear_data(self):
        self.service.get_payroll_page.return_value = {"success": True, "data": [payroll_row()] * 21}
        view = self.view()
        self.assertEqual(view.model.rowCount(), 20)
        self.assertTrue(view.next.isEnabled())
        view.move(1)
        until(lambda: not QtWorker.busy())
        self.assertEqual(self.service.get_payroll_page.call_args.args[1:3], (20, 21))
        self.service.get_payroll_page.return_value = {"success": False, "message": "Offline error"}
        view.load()
        until(lambda: not QtWorker.busy())
        self.assertEqual(view.model.rowCount(), 0)
        self.assertTrue(view.prev.isEnabled())
        self.assertFalse(view.export_button.isEnabled())

    def test_form_dialog_blocks_unknown_messages_and_malformed_results(self):
        dialog = FormDialog(self.parent, "Test", [("name", "Họ tên", "")])
        self.windows.append(dialog)
        for payload in [{"success": False, "message": "PGRST202 SELECT salary token=secret"},
                        "raw error payload", None, ["SQLSTATE 42501"]]:
            dialog.save(lambda payload=payload: payload, self.fail)
            until(lambda: not QtWorker.busy())
            self.assertEqual(dialog.message.text(), SYSTEM_UNAVAILABLE)
            self.assertTrue(dialog.buttons.isEnabled())

    def test_private_load_error_is_custom_and_does_not_enable_empty_form(self):
        self.service.get_employee_private.return_value = {"success": False, "message": "permission denied schema public"}
        dialog = EmployeeDialog(self.parent, ADMIN, payroll_row(), "2026-09-01")
        self.windows.append(dialog)
        until(lambda: not QtWorker.busy())
        self.assertEqual(dialog.message.text(), SYSTEM_UNAVAILABLE)
        self.assertFalse(dialog.save_button.isEnabled())
        self.assertFalse(dialog.pay_button.isEnabled())

    def test_untrusted_payroll_warnings_are_hidden_in_summary_cells_and_tooltips(self):
        row = payroll_row()
        row["warnings"] = ["SELECT salary FROM payroll_snapshots token=secret"]
        row["days"][0]["warning"] = "SQLSTATE 42501"
        self.service.get_payroll_preview.return_value = {"success": True, "data": row}
        dialog = PayrollDetailDialog(self.parent, row, lambda: None)
        self.windows.append(dialog)
        until(lambda: not QtWorker.busy())
        self.assertEqual(dialog.message.toPlainText(), SYSTEM_UNAVAILABLE)
        self.assertEqual(dialog.model.data(dialog.model.index(0, 6)), SYSTEM_UNAVAILABLE)
        self.assertFalse(dialog.final_button.isEnabled())
        self.service.get_payroll_page.return_value = {"success": True, "data": [row]}
        view = self.view()
        self.assertEqual(view.model.data(view.model.index(0, 9), Qt.ItemDataRole.ToolTipRole), SYSTEM_UNAVAILABLE)

    def test_birthday_and_page_errors_use_the_public_filter(self):
        self.service.get_upcoming_birthdays.return_value = {"success": False, "message": "RPC hidden_internal_name"}
        dialog = BirthdayDialog(self.parent)
        self.windows.append(dialog)
        until(lambda: not QtWorker.busy())
        self.assertEqual(dialog.message.text(), SYSTEM_UNAVAILABLE)
        view = self.view()
        view.error("Traceback token=secret")
        self.assertEqual(view.status.text(), SYSTEM_UNAVAILABLE)

    def test_table_renderer_failures_never_emit_raw_diagnostics(self):
        def invalid_renderer(record):
            raise ValueError("token=TOP_SECRET malformed server value")

        model = TableModel([("Test", invalid_renderer)])
        model.replace([{}])
        with self.assertLogs("views_qt.common", level="WARNING") as captured:
            self.assertEqual(model.data(model.index(0, 0)), "—")
            self.assertEqual(model.data(model.index(0, 0), Qt.ItemDataRole.ToolTipRole), SYSTEM_UNAVAILABLE)
        self.assertNotIn("TOP_SECRET", "\n".join(captured.output))
        self.assertNotIn("Traceback", "\n".join(captured.output))

    def test_old_payroll_result_is_ignored_after_filter_changes(self):
        view = self.view()
        release = threading.Event()
        self.addCleanup(release.set)
        self.service.get_payroll_page.side_effect = lambda *args: (release.wait(2), {"success": True, "data": [payroll_row("old")]})[1]
        view.load()
        view.search.setText("new")
        release.set()
        until(lambda: not QtWorker.busy())
        self.assertEqual(view.model.rowCount(), 0)
        self.assertIsNone(view.loaded_filters)
        self.assertFalse(view.export_button.isEnabled())

    def test_private_save_prevents_duplicates_and_restores_controls_after_error(self):
        dialog = EmployeeDialog(self.parent, ADMIN, payroll_row(), "2026-09-01")
        self.windows.append(dialog)
        dialog.show()
        until(lambda: not QtWorker.busy())
        dialog.personal_fields["birth_date"].setText("2000-02-29")
        release = threading.Event()
        self.addCleanup(release.set)
        self.service.save_employee_private.side_effect = lambda *args: (release.wait(2), {"success": False, "message": "Conflict"})[1]
        dialog.save_personal()
        dialog.save_personal()
        self.assertFalse(dialog.save_button.isEnabled())
        release.set()
        until(lambda: not QtWorker.busy())
        self.service.save_employee_private.assert_called_once()
        self.assertEqual(dialog.message.text(), SYSTEM_UNAVAILABLE)
        self.assertTrue(dialog.save_button.isEnabled())
        self.assertEqual(self.service.save_employee_private.call_args.args[2], 0)

    def test_export_fetches_all_pages_in_worker_with_original_filters(self):
        view = self.view()
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def get_page(month, offset, limit, search, branch):
            if limit == 50:
                started.set()
                release.wait(2)
                return {"success": True, "data": [payroll_row()] * (50 if offset == 0 else 1)}
            return {"success": True, "data": [payroll_row()]}

        self.service.get_payroll_page.side_effect = get_page
        expected_month = view.loaded_filters[0]
        with tempfile.TemporaryDirectory() as folder, patch("views_qt.payroll_view.QFileDialog.getSaveFileName",
                return_value=(str(Path(folder) / "payroll.xlsx"), "")), patch("views_qt.payroll_view.export_payroll") as export:
            view.export()
            until(started.is_set)
            view.search.setText("changed after export started")
            release.set()
            until(lambda: not QtWorker.busy())
            self.assertEqual(len(export.call_args.args[1]), 51)
            self.assertEqual(export.call_args.args[2], expected_month)
            self.service.get_payroll_page.assert_any_call(expected_month, 50, 50, "", None)
            self.assertFalse(view.export_button.isEnabled())

    def test_destroying_personnel_dialog_discards_pending_private_data(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def read(user_id):
            started.set()
            release.wait(2)
            return {"success": True, "data": {"details": None, "terms": []}}

        self.service.get_employee_private.side_effect = read
        with patch.object(EmployeeDialog, "loaded") as loaded:
            dialog = EmployeeDialog(self.parent, ADMIN, payroll_row(), "2026-09-01")
            dialog.show()
            until(started.is_set)
            dialog.close()
            APP.processEvents()
            release.set()
            until(lambda: not QtWorker.busy())
            loaded.assert_not_called()

    def test_finalization_uses_latest_signature_and_does_not_retry_stale_data(self):
        dialog = PayrollDetailDialog(self.parent, payroll_row(), lambda: None)
        self.windows.append(dialog)
        dialog.show()
        until(lambda: not QtWorker.busy())
        self.service.finalize_payroll.return_value = {"success": False, "message": "Dữ liệu đã thay đổi"}
        with patch("views_qt.payroll_view.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog.finalize()
            dialog.finalize()
            until(lambda: not QtWorker.busy())
        self.service.finalize_payroll.assert_called_once_with("staff", "2026-09-01", "offline-signature")
        self.assertFalse(dialog.final_button.isEnabled())
        self.assertTrue(dialog.reload_button.isEnabled())

    def test_incomplete_or_current_period_cannot_be_finalized(self):
        for patch_row in [{"warnings": ["Chưa check-out"]}, {"period_closed": False}, {"finalized": True}]:
            self.service.get_payroll_preview.return_value = {"success": True, "data": {**payroll_row(), **patch_row}}
            dialog = PayrollDetailDialog(self.parent, payroll_row(), lambda: None)
            self.windows.append(dialog)
            until(lambda: not QtWorker.busy())
            self.assertFalse(dialog.final_button.isEnabled())
            dialog.finalize()
        self.service.finalize_payroll.assert_not_called()

    def test_birthdays_have_pagination_and_plain_text_names(self):
        self.service.get_upcoming_birthdays.return_value = {"success": True, "data": [
            {"full_name": "<b>Offline</b>", "birth_date": "2000-10-21", "days_until": 0, "age": 26}] * 51}
        dialog = BirthdayDialog(self.parent)
        self.windows.append(dialog)
        until(lambda: not QtWorker.busy())
        self.assertEqual(dialog.model.rowCount(), 50)
        self.assertEqual(dialog.model.data(dialog.model.index(0, 0)), "<b>Offline</b>")
        self.assertTrue(dialog.next.isEnabled())
        dialog.move(1)
        until(lambda: not QtWorker.busy())
        self.service.get_upcoming_birthdays.assert_called_with(50, 51)

    def test_personnel_and_payroll_render_in_both_themes(self):
        view = self.view()
        view.resize(1250, 760)
        view.show()
        dialog = EmployeeDialog(self.parent, ADMIN, payroll_row(), "2026-09-01")
        self.windows.append(dialog)
        dialog.show()
        until(lambda: not QtWorker.busy())
        with tempfile.TemporaryDirectory() as folder:
            for mode in THEMES:
                APP.theme_manager.set_mode(mode)
                APP.processEvents()
                self.assertTrue(view.grab().save(str(Path(folder) / f"{mode}_payroll.png")))
                self.assertTrue(dialog.grab().save(str(Path(folder) / f"{mode}_personnel.png")))
