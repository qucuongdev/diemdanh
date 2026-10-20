import os

os.environ["ATTENDANCE_TESTING"] = "1"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from contextlib import ExitStack
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QCoreApplication, QEvent, QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from core.qt_worker import QtWorker, TaskRunner
from core.supabase_service import SupabaseService
from core.domain import local_now
from views_qt.qt_theme import configure_application
from main import MainWindow

APP = QApplication.instance() or QApplication([])
configure_application(APP)
ADMIN = {"id": "admin", "full_name": "Nguyễn Minh Anh", "role": "admin", "is_active": True, "branch_id": "b"}
STAFF = {"id": "staff", "full_name": "Trần Thảo Linh", "role": "staff", "branch_id": "b", "is_active": True}


def until(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        APP.processEvents()
        QTest.qWait(1)
    APP.processEvents()
    if not predicate():
        raise AssertionError("Timed out waiting for an offline Qt task")


def fake_service():
    service = MagicMock(spec=SupabaseService)
    service.get_branches.return_value = [{"id": "b", "name": "Nhà thuốc An Tâm", "address": "Hồ Chí Minh"}]
    service.get_staff_list.return_value = [{**STAFF, "branches": {"name": "An Tâm"}}]
    service.get_shifts.return_value = [
        {"id": "shift", "name": "Ca sáng", "branch_id": "b", "start_time": "08:00:00", "end_time": "16:00:00"}
    ]
    schedule = {
        "id": "schedule",
        "user_id": "staff",
        "branch_id": "b",
        "work_date": local_now().date().isoformat(),
        "status": "scheduled",
        "profiles": STAFF,
        "shifts": service.get_shifts.return_value[0],
        "attendance": [],
    }
    service.get_schedules_range.return_value = [schedule]
    service.get_today_schedule.return_value = {"success": True, "schedules": [schedule]}
    service.get_leave_requests.return_value = []
    service.get_attendance_proofs.return_value = []
    service.get_allowed_devices.return_value = []
    service.get_monthly_attendance_data.return_value = [schedule]
    service.get_attendance_history.return_value = []
    service.login.return_value = {"success": True, "profile": STAFF}
    service.logout.return_value = None
    return service


class WorkerTests(unittest.TestCase):
    def tearDown(self):
        until(lambda: not QtWorker.busy())
        APP.processEvents()

    def test_callback_runs_on_gui_thread(self):
        owner = QWidget()
        runner = TaskRunner(owner)
        result = []
        runner.submit(
            "read", lambda: 42, lambda value: result.append((value, QThread.currentThread())), self.fail
        )
        until(lambda: bool(result))
        self.assertEqual(result[0], (42, APP.thread()))
        owner.deleteLater()

    def test_latest_request_wins_and_intermediate_requests_are_coalesced(self):
        owner = QWidget()
        runner = TaskRunner(owner)
        release = threading.Event()
        results, called = [], []
        runner.submit("read", lambda: release.wait(2) or 1, results.append, self.fail)
        runner.submit("read", lambda: called.append(2) or 2, results.append, self.fail)
        runner.submit("read", lambda: called.append(3) or 3, results.append, self.fail)
        release.set()
        until(lambda: bool(results))
        self.assertEqual(results, [3])
        self.assertEqual(called, [3])
        owner.deleteLater()

    def test_destroyed_owner_never_receives_result(self):
        owner = QWidget()
        runner = TaskRunner(owner)
        release = threading.Event()
        results = []
        runner.submit("read", lambda: release.wait(2), results.append, results.append)
        owner.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        release.set()
        until(lambda: not QtWorker.busy())
        self.assertEqual(results, [])

    def test_exception_is_sanitized_and_duplicate_mutations_rejected(self):
        owner = QWidget()
        runner = TaskRunner(owner)
        release = threading.Event()
        errors = []

        def work():
            release.wait(2)
            raise RuntimeError("token=TOP_SECRET")

        self.assertTrue(runner.submit("save", work, self.fail, errors.append, replace=False))
        self.assertFalse(runner.submit("save", lambda: 2, self.fail, self.fail, replace=False))
        release.set()
        until(lambda: bool(errors))
        self.assertNotIn("TOP_SECRET", errors[0])
        owner.deleteLater()


class UiTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.service = fake_service()
        for target in [
            "main.SupabaseService",
            "views_qt.login_view.SupabaseService",
            "core.supabase_service.SupabaseService",
        ]:
            self.stack.enter_context(patch(target, return_value=self.service))
        for module in ["login_view", "attendance_view", "settings_view"]:
            self.stack.enter_context(
                patch(f"views_qt.{module}.get_hardware_uuid", return_value="device-test")
            )
        self.window = MainWindow()
        self.window.show()

    def tearDown(self):
        self.window.close()
        until(lambda: not self.window.isVisible())
        until(lambda: not QtWorker.busy())
        self.window.deleteLater()
        APP.processEvents()
        self.stack.close()

    def login(self, profile=ADMIN):
        self.window.on_login_success(profile)
        until(lambda: not QtWorker.busy())
        APP.processEvents()

    def test_role_navigation_and_logout_clears_views(self):
        self.login()
        self.assertEqual(len(self.window.main_app_widget.nav_buttons), 5)
        self.window.show_login_view()
        until(lambda: self.window.root_stack.currentIndex() == 0)
        self.service.logout.assert_called()
        self.assertFalse(self.window.main_app_widget.views)
        self.login(STAFF)
        main = self.window.main_app_widget
        self.assertEqual(set(main.nav_buttons), {"attendance", "schedule"})
        main.show_view("settings")
        self.assertNotIn("settings", main.views)

    def test_enter_cannot_start_two_logins_and_password_is_cleared(self):
        login = self.window.login_view
        login.email_entry.setText("staff")
        login.pass_entry.setText("password-for-test")
        login.handle_login()
        login.handle_login()
        until(lambda: self.window.root_stack.currentIndex() == 1)
        self.service.login.assert_called_once()
        self.assertEqual(login.pass_entry.text(), "")

    def test_invalid_profile_rejected_before_navigation(self):
        self.window.on_login_success({**STAFF, "is_active": False})
        self.assertEqual(self.window.root_stack.currentIndex(), 0)
        self.assertFalse(self.window.main_app_widget.views)

    def test_history_uses_ids_even_for_duplicate_names_and_limits_widget_count(self):
        from views_qt.attendance_history_dialog import AttendanceHistoryDialog

        self.service.get_staff_list.return_value = [{**STAFF, "id": "one"}, {**STAFF, "id": "two"}]
        dialog = AttendanceHistoryDialog(self.window, ADMIN, target_user_id="two")
        dialog.open()
        until(lambda: dialog.page.ready and not QtWorker.busy())
        self.assertEqual(dialog.page.staff_combo.currentData(), "two")
        self.service.get_attendance_history.assert_called_with(None, "two", None, 51, 0)
        record = {"profiles": {"full_name": "<b>literal</b>"}, "check_out": None}
        before = len(dialog.findChildren(QWidget))
        dialog.page._render_records([record] * 51)
        self.assertEqual(dialog.page.model.rowCount(), 50)
        self.assertTrue(dialog.page.next_btn.isEnabled())
        self.assertEqual(len(dialog.findChildren(QWidget)), before)
        self.assertEqual(dialog.page.model.data(dialog.page.model.index(0, 0)), "<b>literal</b>")
        dialog.close()

    def test_staff_history_cannot_change_scope(self):
        from views_qt.attendance_history_dialog import AttendanceHistoryDialog

        dialog = AttendanceHistoryDialog(self.window, STAFF, target_user_id="someone-else")
        dialog.open()
        until(lambda: dialog.page.ready and not QtWorker.busy())
        self.service.get_attendance_history.assert_called_with("b", "staff", None, 51, 0)
        self.assertFalse(dialog.page.branch_combo.isEnabled())
        dialog.close()

    def test_failed_attendance_restores_controls(self):
        self.login(STAFF)
        view = self.window.main_app_widget.views["attendance"]
        self.assertTrue(view.btn_check_in.isEnabled())
        self.service.check_in.side_effect = RuntimeError("secret")
        view.handle_check_in()
        self.assertFalse(view.btn_check_in.isEnabled())
        until(lambda: not view.busy)
        self.assertTrue(view.btn_check_in.isEnabled())
        self.assertNotIn("secret", view.status.text())

    def test_report_export_invalidated_when_period_changes(self):
        self.login()
        self.window.main_app_widget.show_view("reports")
        view = self.window.main_app_widget.views["reports"]
        until(lambda: view.search_btn.isEnabled())
        view.load_report_data()
        until(lambda: bool(view.report_data))
        self.assertTrue(view.export_btn.isEnabled())
        view.month_combo.setCurrentIndex((view.month_combo.currentIndex() + 1) % 12)
        self.assertFalse(view.export_btn.isEnabled())
        self.assertEqual(view.report_data, [])

    def test_all_pages_open_offline_and_save_previews(self):
        self.login()
        folder = Path("artifacts/previews")
        folder.mkdir(parents=True, exist_ok=True)
        for key in ["attendance", "schedule", "approval", "reports", "settings"]:
            self.window.main_app_widget.show_view(key)
            until(lambda: not QtWorker.busy())
            QTest.qWait(10)
            self.assertTrue(self.window.grab().save(str(folder / f"{key}.png")))
            self.assertEqual(self.window.main_app_widget.active_nav_key, key)
