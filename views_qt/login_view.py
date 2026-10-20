from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QLineEdit
from core.supabase_service import SupabaseService
from core.hardware import get_hardware_uuid
from core.domain import validate_profile
from core.qt_worker import TaskRunner
from views_qt.common import label, button, StatusLabel
from views_qt.qt_theme import ThemeToggleButton


class LoginView(QWidget):
    login_success = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.supabase = SupabaseService()
        self.tasks = TaskRunner(self)
        self.busy = False
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("LoginCard")
        card.setMinimumWidth(430)
        card.setMaximumWidth(520)
        form = QVBoxLayout(card)
        form.setContentsMargins(32, 32, 32, 32)
        form.setSpacing(14)
        form.addWidget(label("Nhà thuốc · Chấm công", True))
        form.addWidget(label("Đăng nhập để bắt đầu ca làm việc."))
        form.addWidget(label("Tài khoản"))
        self.email_entry = QLineEdit()
        self.email_entry.setPlaceholderText("Email hoặc tên tài khoản")
        form.addWidget(self.email_entry)
        form.addWidget(label("Mật khẩu"))
        self.pass_entry = QLineEdit()
        self.pass_entry.setEchoMode(QLineEdit.EchoMode.Password)
        form.addWidget(self.pass_entry)
        self.error_label = StatusLabel()
        self.error_label.setMaximumWidth(390)
        form.addWidget(self.error_label)
        self.login_btn = button("Đăng nhập", self.handle_login, True)
        form.addWidget(self.login_btn)
        form.addWidget(label("Thiết bị sẽ được kiểm tra sau khi xác thực tài khoản."))
        self.theme_button = ThemeToggleButton(self)
        form.addWidget(self.theme_button, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        self.email_entry.returnPressed.connect(self.handle_login)
        self.pass_entry.returnPressed.connect(self.handle_login)

    def handle_login(self):
        if self.busy:
            return
        email, password = self.email_entry.text().strip(), self.pass_entry.text()
        if not email or not password:
            self.error_label.set_error("Nhập tài khoản và mật khẩu để tiếp tục.")
            return
        if "@" not in email:
            email += "@nhathuoc.com"
        self.busy = True
        self.login_btn.setEnabled(False)
        self.error_label.setText("Đang xác thực…")

        def authenticate():
            result = self.supabase.login(email, password)
            if not result.get("success"):
                return result
            try:
                profile = validate_profile(result.get("profile"))
                if profile["role"] != "admin" and not self.supabase.check_device_permission(
                    profile["branch_id"], get_hardware_uuid()
                ):
                    raise ValueError("Máy này chưa được cấp phép tại chi nhánh của bạn.")
                return {"success": True, "profile": profile}
            except ValueError as exc:
                self.supabase.logout()
                return {"success": False, "message": str(exc)}
            except Exception:
                self.supabase.logout()
                raise

        self.tasks.submit("login", authenticate, self._on_auth_finished, self._on_auth_error, replace=False)

    def _on_auth_finished(self, result):
        self.busy = False
        self.login_btn.setEnabled(True)
        self.pass_entry.clear()
        if result.get("success"):
            self.error_label.clear()
            self.login_success.emit(result["profile"])
        else:
            self.error_label.set_error(result.get("message", "Đăng nhập thất bại."))

    def _on_auth_error(self, message):
        self.busy = False
        self.login_btn.setEnabled(True)
        self.pass_entry.clear()
        self.error_label.set_error(message)
