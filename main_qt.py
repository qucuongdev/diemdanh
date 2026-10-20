import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QMessageBox
)
from PySide6.QtCore import Qt
from core.config import APP_NAME, APP_VERSION
from core.supabase_service import SupabaseService
from views_qt.qt_theme import DARK_STYLESHEET
from views_qt.login_view import LoginView
from views_qt.attendance_view import AttendanceView
from views_qt.schedule_view import ScheduleView
from views_qt.approval_view import ApprovalView
from views_qt.report_view import ReportView
from views_qt.settings_view import SettingsView

class MainAppWidget(QWidget):
    def __init__(self, parent=None, on_logout=None):
        super().__init__(parent)
        self.on_logout = on_logout
        self.current_profile = None
        self.nav_buttons = {}
        self.views = {}
        self.active_nav_key = None

        self.setup_ui()

    def setup_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ================= 1. SIDEBAR (230px) =================
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(230)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(6)

        # Logo
        self.logo_label = QLabel("💊 NHÀ THUỐC")
        self.logo_label.setObjectName("SidebarLogo")
        self.logo_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(self.logo_label)

        # Role Badge
        self.role_badge = QLabel("")
        self.role_badge.setObjectName("RoleBadge")
        self.role_badge.setAlignment(Qt.AlignCenter)
        self.role_badge.setFixedHeight(28)
        sidebar_layout.addWidget(self.role_badge)
        sidebar_layout.addSpacing(10)

        # Menu Buttons Container
        self.menu_container = QWidget()
        self.menu_layout = QVBoxLayout(self.menu_container)
        self.menu_layout.setContentsMargins(0, 0, 0, 0)
        self.menu_layout.setSpacing(6)
        sidebar_layout.addWidget(self.menu_container)

        sidebar_layout.addStretch()

        # Logout Button
        self.btn_logout = QPushButton("🚪  Đăng xuất")
        self.btn_logout.setObjectName("LogoutSidebarBtn")
        self.btn_logout.setFixedHeight(40)
        self.btn_logout.clicked.connect(self.handle_logout)
        sidebar_layout.addWidget(self.btn_logout)

        root_layout.addWidget(self.sidebar)

        # ================= 2. CONTENT STACK =================
        self.content_stack = QStackedWidget()
        root_layout.addWidget(self.content_stack)

    def configure_user(self, profile):
        self.current_profile = profile
        role = profile.get("role", "staff")

        # Update role badge
        role_label = {
            "admin": "👑 CHỦ CHUỖI",
            "storemanager": "👔 CỬA HÀNG TRƯỞNG",
            "staff": "💊 DƯỢC SĨ"
        }.get(role, role.upper())
        self.role_badge.setText(role_label)

        # Clear existing buttons
        for btn in self.nav_buttons.values():
            btn.setParent(None)
        self.nav_buttons.clear()

        # Clear existing views
        while self.content_stack.count() > 0:
            w = self.content_stack.widget(0)
            self.content_stack.removeWidget(w)
        self.views.clear()

        # Build role-based buttons
        self.add_nav_button("attendance", "🕒  Điểm danh quầy", lambda: self.show_view("attendance"))
        self.add_nav_button("schedule", "📅  Lịch làm việc", lambda: self.show_view("schedule"))

        if role in ("storemanager", "admin"):
            self.add_nav_button("approval", "📋  Duyệt yêu cầu", lambda: self.show_view("approval"))
            self.add_nav_button("reports", "📊  Báo cáo Excel", lambda: self.show_view("reports"))

        if role == "admin":
            self.add_nav_button("settings", "⚙️  Quản trị hệ thống", lambda: self.show_view("settings"))

        # Pre-instantiate and cache the primary view (attendance)
        self.show_view("attendance")

    def add_nav_button(self, key, text, command):
        btn = QPushButton(text)
        btn.setProperty("class", "NavButton")
        btn.setFixedHeight(42)
        btn.clicked.connect(command)
        self.menu_layout.addWidget(btn)
        self.nav_buttons[key] = btn

    def set_active_nav(self, active_key):
        self.active_nav_key = active_key
        for key, btn in self.nav_buttons.items():
            is_active = (key == active_key)
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def show_view(self, view_name):
        self.set_active_nav(view_name)

        if view_name not in self.views:
            if view_name == "attendance":
                view = AttendanceView(parent=self, current_profile=self.current_profile)
                view.logout_requested.connect(self.handle_logout)
            elif view_name == "schedule":
                view = ScheduleView(parent=self, current_profile=self.current_profile)
            elif view_name == "approval":
                view = ApprovalView(parent=self, current_profile=self.current_profile)
            elif view_name == "reports":
                view = ReportView(parent=self, current_profile=self.current_profile)
            elif view_name == "settings":
                view = SettingsView(parent=self, current_profile=self.current_profile)
            else:
                return

            self.views[view_name] = view
            self.content_stack.addWidget(view)

        self.content_stack.setCurrentWidget(self.views[view_name])

    def handle_logout(self):
        if self.on_logout:
            self.on_logout()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION} (PySide6 Edition)")
        self.resize(1280, 820)
        self.setMinimumSize(1100, 700)

        self.supabase = SupabaseService()
        self.current_profile = None

        # Root stacked widget
        self.root_stack = QStackedWidget()
        self.root_stack.setObjectName("CentralWidget")
        self.setCentralWidget(self.root_stack)

        # Page 0: Login View
        self.login_view = LoginView(parent=self)
        self.login_view.login_success.connect(self.on_login_success)
        self.root_stack.addWidget(self.login_view)

        # Page 1: Main Application
        self.main_app_widget = MainAppWidget(parent=self, on_logout=self.show_login_view)
        self.root_stack.addWidget(self.main_app_widget)

        self.show_login_view()

    def show_login_view(self):
        self.current_profile = None
        self.root_stack.setCurrentIndex(0)

    def on_login_success(self, profile):
        self.current_profile = profile
        self.main_app_widget.configure_user(profile)
        self.root_stack.setCurrentIndex(1)


def main():
    # Enable High DPI
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
