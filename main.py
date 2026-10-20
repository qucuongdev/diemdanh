"""Supported PySide6 application entry point."""

import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget
from core.config import APP_NAME, APP_VERSION
from core.domain import ROLES, validate_profile
from core.qt_worker import QtWorker, TaskRunner
from core.supabase_service import SupabaseService
from views_qt.common import label, button
from views_qt.qt_theme import configure_application, ThemeToggleButton
from views_qt.login_view import LoginView


class MainAppWidget(QWidget):
    def __init__(self, parent=None, on_logout=None):
        super().__init__(parent)
        self.on_logout = on_logout
        self.views, self.nav_buttons = {}, {}
        self.current_profile = None
        self.active_nav_key = None
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 28, 16, 20)
        logo = label("NHÀ THUỐC")
        logo.setObjectName("SidebarLogo")
        layout.addWidget(logo)
        layout.addWidget(label("Quản lý chấm công"))
        self.role_badge = label()
        layout.addWidget(self.role_badge)
        layout.addSpacing(28)
        self.menu_layout = QVBoxLayout()
        layout.addLayout(self.menu_layout)
        layout.addStretch()
        self.theme_button = ThemeToggleButton(self)
        layout.addWidget(self.theme_button)
        layout.addWidget(button("Đăng xuất", self.handle_logout))
        root.addWidget(sidebar)
        self.content_stack = QStackedWidget()
        root.addWidget(self.content_stack, 1)

    def clear_session(self):
        for runner in self.findChildren(TaskRunner):
            runner.invalidate()
        for btn in self.nav_buttons.values():
            self.menu_layout.removeWidget(btn)
            btn.deleteLater()
        self.nav_buttons.clear()
        while self.content_stack.count():
            widget = self.content_stack.widget(0)
            self.content_stack.removeWidget(widget)
            widget.deleteLater()
        self.views.clear()
        self.current_profile = None
        self.active_nav_key = None

    def configure_user(self, profile):
        validate_profile(profile)
        self.clear_session()
        self.current_profile = profile
        role = profile["role"]
        self.role_badge.setText(ROLES[role])
        items = [("attendance", "Check-in / Check-out"), ("schedule", "Lịch làm việc")]
        if role in ("admin", "storemanager"):
            items += [("approval", "Duyệt yêu cầu"), ("reports", "Báo cáo")]
        if role == "admin":
            items += [("settings", "Quản trị")]
        for key, text in items:
            btn = button(text, lambda checked=False, key=key: self.show_view(key))
            self.menu_layout.addWidget(btn)
            self.nav_buttons[key] = btn
        self.show_view("attendance")

    def show_view(self, key):
        # Guard direct calls as well as visible navigation.
        if key not in self.nav_buttons:
            return
        if self.active_nav_key != key:
            previous = self.views.get(self.active_nav_key)
            if previous is not None and hasattr(previous, "on_hide"):
                previous.on_hide()
        if key not in self.views:
            if key == "attendance":
                from views_qt.attendance_view import AttendanceView

                view = AttendanceView(self, self.current_profile)
            elif key == "schedule":
                from views_qt.schedule_view import ScheduleView

                view = ScheduleView(self, self.current_profile)
            elif key == "approval":
                from views_qt.approval_view import ApprovalView

                view = ApprovalView(self, self.current_profile)
            elif key == "reports":
                from views_qt.report_view import ReportView

                view = ReportView(self, self.current_profile)
            else:
                from views_qt.settings_view import SettingsView

                view = SettingsView(self, self.current_profile)
            self.views[key] = view
            self.content_stack.addWidget(view)
        self.content_stack.setCurrentWidget(self.views[key])
        self.active_nav_key = key
        for name, btn in self.nav_buttons.items():
            btn.setProperty("active", name == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if hasattr(self.views[key], "on_show"):
            self.views[key].on_show()

    def handle_logout(self):
        if self.on_logout:
            self.on_logout()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} · {APP_VERSION}")
        self.resize(1280, 820)
        self.setMinimumSize(1000, 680)
        self.supabase = SupabaseService()
        self.tasks = TaskRunner(self)
        self.current_profile = None
        self._closing = False
        self._logging_out = False
        self._allow_close = False
        self.root_stack = QStackedWidget()
        self.setCentralWidget(self.root_stack)
        self.login_view = LoginView(self)
        self.login_view.login_success.connect(self.on_login_success)
        self.root_stack.addWidget(self.login_view)
        self.main_app_widget = MainAppWidget(self, on_logout=self.show_login_view)
        self.root_stack.addWidget(self.main_app_widget)
        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(50)
        self._drain_timer.timeout.connect(self._drain)

    def on_login_success(self, profile):
        try:
            validate_profile(profile)
        except ValueError as exc:
            self.login_view._on_auth_error(str(exc))
            self.show_login_view()
            return
        self.current_profile = profile
        self.main_app_widget.configure_user(profile)
        self.root_stack.setCurrentIndex(1)

    def show_login_view(self):
        if self._logging_out:
            return
        self._logging_out = True
        self.current_profile = None
        self.main_app_widget.clear_session()
        self.setEnabled(False)
        self._drain_timer.start()

    def _drain(self):
        if QtWorker.busy():
            return
        self._drain_timer.stop()
        self.tasks.submit("logout", self.supabase.logout, self._logged_out, self._logged_out, replace=False)

    def _logged_out(self, _result=None):
        self._logging_out = False
        if self._closing:
            self._allow_close = True
            self.close()
        else:
            self.login_view.pass_entry.clear()
            self.login_view.error_label.clear()
            self.root_stack.setCurrentIndex(0)
            self.setEnabled(True)
            self.login_view.email_entry.setFocus()

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        self._closing = True
        self.login_view.tasks.invalidate()
        self.show_login_view()


def main():
    app = QApplication(sys.argv)
    configure_application(app)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
