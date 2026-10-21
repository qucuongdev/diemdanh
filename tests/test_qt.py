import os

os.environ["ATTENDANCE_TESTING"] = "1"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from contextlib import ExitStack
from pathlib import Path
import threading
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QCoreApplication, QEvent, QThread, QSettings, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from core.qt_worker import QtWorker, TaskRunner
from core.supabase_service import SupabaseService
from core.domain import local_now
from views_qt.qt_theme import configure_application, ThemeManager, THEMES
from main import MainWindow

APP = QApplication.instance() or QApplication([])
configure_application(APP)
ADMIN = {"id": "admin", "full_name": "Nguyễn Minh Anh", "role": "admin", "is_active": True, "branch_id": "b"}
STAFF = {"id": "staff", "full_name": "Trần Thảo Linh", "role": "staff", "branch_id": "b", "is_active": True}


class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / "appearance.ini")
        self.settings = QSettings(self.path, QSettings.Format.IniFormat)
        self.managers = []

    def manager(self, settings=None):
        manager = ThemeManager(APP, self.settings if settings is None else settings)
        self.managers.append(manager)
        return manager

    def tearDown(self):
        for manager in self.managers:
            manager.deleteLater()
        APP.theme_manager.apply()
        APP.processEvents()

    def test_theme_preference_is_restored_from_isolated_settings(self):
        manager = self.manager()
        manager.set_mode("light")
        self.settings.sync()
        restored = self.manager(QSettings(self.path, QSettings.Format.IniFormat))
        self.assertEqual(restored.mode, "light")
        self.assertGreater(APP.palette().color(QPalette.ColorRole.Window).lightness(), 200)
        restored.set_mode("dark")
        self.assertLess(APP.palette().color(QPalette.ColorRole.Window).lightness(), 60)

    def test_invalid_saved_theme_falls_back_and_invalid_updates_are_rejected(self):
        self.settings.setValue("appearance/theme", ["invalid"])
        manager = self.manager()
        self.assertEqual(manager.mode, "dark")
        with self.assertRaises(ValueError):
            manager.set_mode("invalid")
        self.assertEqual(manager.mode, "dark")

    def test_palette_has_readable_text_and_disabled_controls_in_both_modes(self):
        def luminance(color):
            channels = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                        for value in (color.redF(), color.greenF(), color.blueF())]
            return sum(value * weight for value, weight in zip(channels, (0.2126, 0.7152, 0.0722), strict=True))

        manager = self.manager()
        for mode in THEMES:
            manager.set_mode(mode)
            palette = APP.palette()
            for foreground, background in ((QPalette.ColorRole.Text, QPalette.ColorRole.Base),
                                           (QPalette.ColorRole.HighlightedText, QPalette.ColorRole.Highlight)):
                light, dark = sorted((luminance(palette.color(foreground)), luminance(palette.color(background))))[::-1]
                self.assertGreaterEqual((light + 0.05) / (dark + 0.05), 4.5)
            self.assertNotEqual(palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text),
                                palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text))


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
    service.get_upcoming_birthdays.return_value = {"success": True, "data": []}
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

    def test_gui_callback_failure_routes_to_custom_error_without_raw_traceback(self):
        from core.ui_messages import SYSTEM_UNAVAILABLE
        owner = QWidget()
        runner = TaskRunner(owner)
        errors = []

        def broken_callback(value):
            raise ValueError("SQL query token=TOP_SECRET")

        with self.assertLogs("core.qt_worker", level="WARNING") as captured:
            runner.submit("read", lambda: 42, broken_callback, errors.append)
            until(lambda: bool(errors))
        self.assertEqual(errors, [SYSTEM_UNAVAILABLE])
        self.assertNotIn("TOP_SECRET", "\n".join(captured.output))
        self.assertNotIn("Traceback", "\n".join(captured.output))
        owner.deleteLater()

    def test_error_callback_failure_is_not_logged_with_server_payload(self):
        owner = QWidget()
        runner = TaskRunner(owner)

        def broken_error(message):
            raise RuntimeError("DO_NOT_DISPLAY raw server exception")

        with self.assertLogs("core.qt_worker", level="WARNING") as captured:
            runner.submit("read", lambda: None, lambda value: (_ for _ in ()).throw(ValueError()), broken_error)
            until(lambda: not QtWorker.busy())
        self.assertNotIn("DO_NOT_DISPLAY", "\n".join(captured.output))
        self.assertNotIn("Traceback", "\n".join(captured.output))
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
        APP.theme_manager.set_mode("dark")
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
        APP.theme_manager.set_mode("dark")

    def login(self, profile=ADMIN):
        self.window.on_login_success(profile)
        until(lambda: not QtWorker.busy())
        APP.processEvents()

    def test_role_navigation_and_logout_clears_views(self):
        self.login()
        self.assertEqual(len(self.window.main_app_widget.nav_buttons), 6)
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

    def test_login_card_is_centered_and_has_bounded_width(self):
        from PySide6.QtWidgets import QFrame

        card = self.window.login_view.findChild(QFrame, "LoginCard")
        self.assertLessEqual(card.width(), 520)
        self.assertAlmostEqual(card.geometry().center().x(), self.window.login_view.rect().center().x(), delta=2)
        folder = Path("artifacts/previews")
        folder.mkdir(parents=True, exist_ok=True)
        self.assertTrue(self.window.grab().save(str(folder / "login.png")))

    def test_unexpected_device_check_failure_logs_out_and_restores_login(self):
        for failure in [RuntimeError("secret device failure"), ValueError("secret hardware system failure")]:
            self.service.logout.reset_mock()
            self.service.check_device_permission.side_effect = failure
            login = self.window.login_view
            login.email_entry.setText("staff")
            login.pass_entry.setText("test-password")
            login.handle_login()
            until(lambda login=login: not login.busy)
            self.service.logout.assert_called_once()
            self.assertEqual(self.window.root_stack.currentIndex(), 0)
            self.assertTrue(login.login_btn.isEnabled())
            self.assertEqual(login.pass_entry.text(), "")
            self.assertNotIn("secret", login.error_label.text())

    def test_attendance_rejection_remains_visible_without_being_overwritten(self):
        self.login(STAFF)
        view = self.window.main_app_widget.views["attendance"]
        self.service.check_in.return_value = {"success": False, "message": "Thiết bị chưa được cấp phép."}
        before = self.service.get_today_schedule.call_count
        view.handle_check_in()
        until(lambda: not view.busy)
        self.assertIn("chưa được cấp phép", view.status.text())
        self.assertEqual(self.service.get_today_schedule.call_count, before)
        self.assertTrue(view.btn_check_in.isEnabled())

    def test_attendance_success_message_survives_schedule_reload(self):
        self.login(STAFF)
        view = self.window.main_app_widget.views["attendance"]
        self.service.check_in.return_value = {"success": True, "message": "Đã vào ca. Đi muộn 2 phút."}
        schedule = self.service.get_today_schedule.return_value["schedules"][0]
        self.service.get_today_schedule.return_value = {"success": True, "schedules": [
            {**schedule, "attendance": {"id": "a", "check_in": "2026-10-21T01:01:30Z",
                                       "is_late": True, "late_minutes": 2}},
        ]}
        view.handle_check_in()
        until(lambda: not view.busy and not view.loading)
        self.assertEqual(view.status.text(), "Check-in thành công.")
        self.assertIn("Muộn 2 phút", view.detail.text())
        self.assertIn("08:01:30", view.detail.toolTip())

    def test_failed_schedule_refresh_does_not_leave_actionable_old_shift(self):
        self.login(STAFF)
        view = self.window.main_app_widget.views["attendance"]
        self.service.get_today_schedule.side_effect = RuntimeError("secret")
        view.load_schedule()
        until(lambda: not view.loading)
        self.assertEqual(view.schedules, [])
        self.assertFalse(view.btn_check_in.isEnabled())
        self.assertFalse(view.btn_check_out.isEnabled())
        self.assertIn("Không thể xác định", view.detail.text())

    def test_history_failed_refresh_clears_previous_records_and_totals(self):
        from views_qt.attendance_history_dialog import AttendanceHistoryDialog

        dialog = AttendanceHistoryDialog(self.window, ADMIN)
        dialog.open()
        until(lambda: dialog.page.ready and not QtWorker.busy())
        dialog.page._render_records([{"check_in": None}])
        self.service.get_attendance_history.side_effect = RuntimeError("secret")
        dialog.page.reset()
        until(lambda: not QtWorker.busy())
        self.assertEqual(dialog.page.model.rowCount(), 0)
        self.assertEqual(dialog.page.summary.text(), "")
        self.assertFalse(dialog.page.next_btn.isEnabled())
        dialog.close()

    def test_report_failed_reload_removes_previous_totals_and_export(self):
        self.login()
        self.window.main_app_widget.show_view("reports")
        view = self.window.main_app_widget.views["reports"]
        until(lambda: view.search_btn.isEnabled())
        view.load_report_data()
        until(lambda: bool(view.report_data))
        self.service.get_monthly_attendance_data.side_effect = RuntimeError("secret")
        view.load_report_data()
        until(lambda: not QtWorker.busy())
        self.assertEqual(view.report_data, [])
        self.assertEqual(view.model.rowCount(), 0)
        self.assertFalse(view.export_btn.isEnabled())

    def test_settings_cannot_edit_cached_rows_during_refresh(self):
        self.login()
        self.window.main_app_widget.show_view("settings")
        view = self.window.main_app_widget.views["settings"]
        until(lambda: view.ready)
        release = threading.Event()
        self.addCleanup(release.set)
        records = self.service.get_branches.return_value
        self.service.get_branches.side_effect = lambda *args: (release.wait(2), records)[1]
        view.refresh()
        view.kind.setCurrentIndex(1)
        self.assertEqual(view.model.rowCount(), 0)
        self.assertFalse(view.edit_btn.isEnabled())
        self.assertFalse(view.delete_btn.isEnabled())
        release.set()
        until(lambda: view.ready)

    def test_switching_back_to_schedule_refreshes_changes_from_other_pages(self):
        self.login()
        main = self.window.main_app_widget
        main.show_view("schedule")
        view = main.views["schedule"]
        until(lambda: view.ready and not QtWorker.busy())
        previous = self.service.get_schedules_range.call_count
        main.show_view("attendance")
        main.show_view("schedule")
        until(lambda: not QtWorker.busy())
        self.assertGreater(self.service.get_schedules_range.call_count, previous)

    def test_form_preserves_password_whitespace(self):
        from views_qt.common import FormDialog

        dialog = FormDialog(self.window, "Test", [("password", "Mật khẩu", ""), ("name", "Tên", "")])
        dialog.fields["password"].setText(" test password ")
        dialog.fields["name"].setText(" Nhân viên ")
        self.assertEqual(dialog.values(), {"password": " test password ", "name": "Nhân viên"})
        dialog.deleteLater()

    def test_duplicate_mutation_keeps_controls_disabled_until_first_finishes(self):
        self.login()
        view = self.window.main_app_widget.views["attendance"]
        release = threading.Event()
        self.addCleanup(release.set)
        results = []
        controls = [view.btn_upload_proof]
        def work():
            release.wait(2)
            return {"success": True}

        self.assertTrue(view.mutate(work, lambda: results.append(True), controls))
        self.assertFalse(view.mutate(work, lambda: self.fail("Duplicate mutation"), controls))
        self.assertFalse(view.btn_upload_proof.isEnabled())
        release.set()
        until(lambda: bool(results))
        self.assertTrue(view.btn_upload_proof.isEnabled())

    def test_approval_self_review_is_disabled_and_direct_call_is_ignored(self):
        self.login()
        main = self.window.main_app_widget
        main.show_view("approval")
        view = main.views["approval"]
        until(lambda: not view.busy)
        view.model.replace([{"id": "r", "user_id": ADMIN["id"], "status": "pending"}])
        view.table.selectRow(0)
        view.selection_changed()
        self.assertFalse(view.approve_btn.isEnabled())
        self.assertFalse(view.reject_btn.isEnabled())
        view.review("approved")
        self.service.review_leave_request.assert_not_called()

    def test_failed_review_restores_pagination(self):
        self.login()
        self.service.get_leave_requests.return_value = [
            {"id": "r", "user_id": STAFF["id"], "status": "pending"}
        ] * 51
        self.window.main_app_widget.show_view("approval")
        view = self.window.main_app_widget.views["approval"]
        until(lambda: not view.busy)
        self.assertTrue(view.next_btn.isEnabled())
        view.table.selectRow(0)
        self.service.review_leave_request.side_effect = RuntimeError("secret")
        view.review("approved")
        until(lambda: not view.busy)
        self.assertTrue(view.next_btn.isEnabled())
        self.assertTrue(view.approve_btn.isEnabled())
        self.assertNotIn("secret", view.status.text())

    def test_proof_url_result_does_not_open_browser_after_leaving_page(self):
        self.login()
        main = self.window.main_app_widget
        main.show_view("approval")
        view = main.views["approval"]
        until(lambda: not view.busy)
        self.service.get_attendance_proofs.return_value = [
            {"id": "p", "user_id": STAFF["id"], "status": "pending", "image_url": "staff/proof.jpg"}
        ]
        view.kind.setCurrentIndex(1)
        until(lambda: not view.busy)
        view.table.selectRow(0)
        release = threading.Event()
        self.addCleanup(release.set)
        self.service.get_proof_url.side_effect = lambda *args: (release.wait(2), "https://offline.example/proof")[1]
        with patch("views_qt.approval_view.QDesktopServices.openUrl") as open_url:
            view.open_image()
            main.show_view("attendance")
            release.set()
            until(lambda: not QtWorker.busy())
            open_url.assert_not_called()

    def test_invalid_profile_rejected_before_navigation(self):
        self.window.on_login_success({**STAFF, "is_active": False})
        self.assertEqual(self.window.root_stack.currentIndex(), 0)
        self.assertFalse(self.window.main_app_widget.views)

    def test_login_theme_toggle_preserves_fields_and_updates_both_buttons(self):
        login = self.window.login_view
        login.email_entry.setText("offline@example.com")
        login.pass_entry.setText("test-password")
        login.theme_button.click()
        self.assertEqual(APP.theme_manager.mode, "light")
        self.assertEqual(login.theme_button.text(), "Giao diện tối")
        self.assertEqual(self.window.main_app_widget.theme_button.text(), "Giao diện tối")
        self.assertEqual(login.pass_entry.text(), "test-password")
        self.assertEqual(login.email_entry.text(), "offline@example.com")
        self.assertEqual(self.window.root_stack.currentIndex(), 0)
        self.service.login.assert_not_called()

    def test_theme_switch_keeps_calendar_filters_selection_and_records_without_requests(self):
        self.login()
        main = self.window.main_app_widget
        main.show_view("schedule")
        view = main.views["schedule"]
        until(lambda: view.ready and not QtWorker.busy())
        selected = view.calendar.selectedDate()
        filters = (view.branch_combo.currentData(), view.staff_combo.currentData())
        records = list(view.model.records)
        calls = list(self.service.mock_calls)
        main.theme_button.click()
        self.assertEqual(APP.theme_manager.mode, "light")
        self.assertEqual(main.active_nav_key, "schedule")
        self.assertEqual(view.calendar.selectedDate(), selected)
        self.assertEqual((view.branch_combo.currentData(), view.staff_combo.currentData()), filters)
        self.assertEqual(view.model.records, records)
        self.assertEqual(self.service.mock_calls, calls)
        for marked in view._marked_dates:
            self.assertEqual(view.calendar.dateTextFormat(marked).background().color().name(),
                             THEMES["light"]["selection"])

    def test_theme_switch_does_not_enable_attendance_while_schedule_is_loading(self):
        self.login(STAFF)
        main = self.window.main_app_widget
        view = main.views["attendance"]
        result = self.service.get_today_schedule.return_value
        release = threading.Event()
        self.addCleanup(release.set)
        self.service.get_today_schedule.side_effect = lambda *args: (release.wait(2), result)[1]
        view.load_schedule()
        main.theme_button.click()
        self.assertFalse(view.btn_check_in.isEnabled())
        self.assertFalse(view.btn_check_out.isEnabled())
        self.assertTrue(view.loading)
        release.set()
        until(lambda: not view.loading)
        self.assertTrue(view.btn_check_in.isEnabled())

    def test_checkin_labels_version_and_responsive_card_width(self):
        from PySide6.QtWidgets import QFrame

        self.window.resize(1900, 1000)
        self.login(STAFF)
        view = self.window.main_app_widget.views["attendance"]
        APP.processEvents()
        self.assertTrue(self.window.windowTitle().endswith("1.0.0"))
        self.assertEqual(view.btn_check_in.text(), "Check-in")
        self.assertEqual(view.btn_check_out.text(), "Check-out")
        self.assertRegex(view.clock_label.text(), r"^\d{2}:\d{2}$")
        card = view.findChild(QFrame, "Card")
        self.assertGreater(card.width(), 700)
        self.assertLessEqual(card.width(), 1100)

    def test_table_prioritizes_name_and_branch_in_wide_window(self):
        self.window.resize(1900, 1000)
        self.login()
        self.window.main_app_widget.show_view("settings")
        view = self.window.main_app_widget.views["settings"]
        until(lambda: view.ready and not QtWorker.busy())
        view.kind.setCurrentIndex(3)
        APP.processEvents()
        self.assertGreater(view.table.columnWidth(0), view.table.columnWidth(4))
        self.assertGreater(view.table.columnWidth(1), view.table.columnWidth(4))
        self.assertLess(view.table.columnWidth(4), view.table.viewport().width() * 0.4)

    def test_history_work_hours_and_status_colors_follow_theme(self):
        from PySide6.QtGui import QColor
        from views_qt.attendance_history_dialog import AttendanceHistoryDialog

        dialog = AttendanceHistoryDialog(self.window, ADMIN)
        self.addCleanup(dialog.close)
        until(lambda: dialog.page.ready and not QtWorker.busy())
        model = dialog.page.model
        base = {"check_in": "2026-10-21T01:00:00Z", "check_out": "2026-10-21T09:00:00Z",
                "schedules": {"work_date": "2026-10-21", "shifts": {
                    "start_time": "08:00:00", "end_time": "16:00:00"}}}
        model.replace([base, {**base, "check_in": "2026-10-21T01:15:00Z"},
                       {**base, "check_out": None}, {**base, "schedules": None},
                       {**base, "check_in": "2026-10-21T02:00:00Z"},
                       {**base, "check_in": "2026-10-21T08:01:00Z"}])
        columns = {col[0]: i for i, col in enumerate(model.columns)}
        hours, status = columns["Giờ làm"], columns["Trạng thái"]
        for row, expected_hours, expected_status in [
            (0, "08:00", "● Done"), (1, "07:45", "● Thiếu 15 phút"),
            (2, "—", "Chưa check-out"), (3, "—", "Không đủ dữ liệu"),
            (4, "07:00", "● Thiếu 01:00"), (5, "59 phút", "● Thiếu 07:01"),
        ]:
            self.assertEqual(model.data(model.index(row, hours)), expected_hours)
            self.assertEqual(model.data(model.index(row, status)), expected_status)
        for mode, colors in THEMES.items():
            APP.theme_manager.set_mode(mode)
            APP.processEvents()
            for row, token in [(0, "success"), (1, "error")]:
                self.assertEqual(model.data(model.index(row, status), Qt.ItemDataRole.ForegroundRole),
                                 QColor(colors[token]))
            self.assertIsNone(model.data(model.index(2, status), Qt.ItemDataRole.ForegroundRole))

    def test_form_buttons_are_vietnamese_in_both_themes(self):
        from PySide6.QtWidgets import QDialogButtonBox
        from views_qt.common import FormDialog

        dialog = FormDialog(self.window, "Test", [("name", "Họ tên", "Nhân viên")])
        dialog.show()
        for mode in THEMES:
            APP.theme_manager.set_mode(mode)
            APP.processEvents()
            self.assertEqual(dialog.buttons.button(QDialogButtonBox.StandardButton.Save).text(), "Lưu")
            self.assertEqual(dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).text(), "Hủy")
            self.assertEqual(dialog.fields["name"].text(), "Nhân viên")
        dialog.close()
        dialog.deleteLater()

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
        dialog.page._render_records([{"check_in": "2026-10-20T18:00:01Z"}])
        self.assertEqual(dialog.page.model.data(dialog.page.model.index(0, 4)), "01:00")
        self.assertEqual(dialog.page.model.data(dialog.page.model.index(0, 4), Qt.ItemDataRole.ToolTipRole),
                         "21/10/2026 01:00:01 · Giờ Việt Nam")
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
        folder = Path("artifacts/previews")
        folder.mkdir(parents=True, exist_ok=True)
        for mode in THEMES:
            APP.theme_manager.set_mode(mode)
            APP.processEvents()
            self.assertTrue(self.window.grab().save(str(folder / f"{mode}_login.png")))
        schedule = self.service.get_today_schedule.return_value["schedules"][0]
        today = local_now().date().isoformat()
        attendance = {"id": "a", "check_in": f"{today}T02:05:00Z", "check_out": f"{today}T09:00:00Z",
                      "is_late": True, "late_minutes": 65}
        schedule.update(status="completed", attendance=attendance)
        self.login()
        for mode in THEMES:
            APP.theme_manager.set_mode(mode)
            for key in ["attendance", "schedule", "approval", "reports", "settings"]:
                self.window.main_app_widget.show_view(key)
                until(lambda: not QtWorker.busy())
                if key == "reports":
                    view = self.window.main_app_widget.views[key]
                    view.load_report_data()
                    until(lambda view=view: bool(view.report_data))
                APP.processEvents()
                self.assertTrue(self.window.grab().save(str(folder / f"{mode}_{key}.png")))
                self.assertEqual(self.window.main_app_widget.active_nav_key, key)
                if mode == "dark":
                    self.assertTrue(self.window.grab().save(str(folder / f"{key}.png")))
        from views_qt.attendance_history_dialog import AttendanceHistoryDialog
        from views_qt.common import FormDialog

        self.service.get_attendance_history.return_value = [
            {**attendance, "profiles": STAFF, "branches": {"name": "Nhà thuốc An Tâm"},
             "schedules": {"work_date": today, "shifts": {"name": "Ca sáng"}}}
        ]
        history = AttendanceHistoryDialog(self.window, ADMIN)
        history.open()
        until(lambda: history.page.ready and not QtWorker.busy())
        form = FormDialog(self.window, "Thêm nhân sự", [
            ("email", "Email", "offline@example.com"), ("password", "Mật khẩu", ""),
            ("name", "Họ tên", "Nhân viên thử nghiệm"),
        ])
        form.show()
        for mode in THEMES:
            APP.theme_manager.set_mode(mode)
            APP.processEvents()
            self.assertTrue(history.grab().save(str(folder / f"{mode}_history.png")))
            self.assertTrue(form.grab().save(str(folder / f"{mode}_form.png")))
        history.close()
        form.close()
        form.deleteLater()
