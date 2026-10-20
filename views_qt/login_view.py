from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame
)
from PySide6.QtCore import Signal, Qt
from core.hardware import get_hardware_uuid
from core.supabase_service import SupabaseService
from core.qt_worker import QtWorker

class LoginView(QWidget):
    login_success = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.supabase = SupabaseService()
        self.device_uuid = get_hardware_uuid()
        self.worker = None

        self.setup_ui()

    def setup_ui(self):
        # Layout căn giữa toàn bộ cửa sổ
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Card chứa Form đăng nhập (420px)
        self.card = QFrame()
        self.card.setObjectName("LoginCard")
        self.card.setProperty("class", "CardFrame")
        self.card.setFixedWidth(420)
        self.card.setStyleSheet("""
            QFrame#LoginCard {
                background-color: #242424;
                border: 1px solid #333333;
                border-radius: 16px;
                padding: 30px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setSpacing(12)

        # Tiêu đề & Phụ đề
        lbl_title = QLabel("NHÀ THUỐC ĐIỂM DANH")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #FFFFFF;")
        card_layout.addWidget(lbl_title)

        lbl_sub = QLabel("Hệ thống chấm công quầy chuỗi nhà thuốc")
        lbl_sub.setAlignment(Qt.AlignCenter)
        lbl_sub.setStyleSheet("font-size: 12px; color: gray; margin-bottom: 10px;")
        card_layout.addWidget(lbl_sub)

        # Khung bảo mật phần cứng máy quầy (Hardware UUID)
        dev_box = QFrame()
        dev_box.setStyleSheet("background-color: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 8px; padding: 8px;")
        dev_layout = QVBoxLayout(dev_box)
        dev_layout.setSpacing(4)

        lbl_dev_title = QLabel("🔒 XÁC THỰC PHẦN CỨNG MÁY QUẦY")
        lbl_dev_title.setStyleSheet("color: #28A745; font-size: 10px; font-weight: bold;")
        dev_layout.addWidget(lbl_dev_title)

        masked_uuid = f"••••-••••-••••-{self.device_uuid[-6:]}" if len(self.device_uuid) > 6 else "••••••••"
        lbl_dev_val = QLabel(f"Trạng thái: Đã khóa theo máy quầy ({masked_uuid})")
        lbl_dev_val.setStyleSheet("font-family: Consolas, monospace; font-size: 10px; color: #888888;")
        dev_layout.addWidget(lbl_dev_val)

        card_layout.addWidget(dev_box)

        # Input Email
        lbl_email = QLabel("Tài khoản Email:")
        lbl_email.setStyleSheet("font-size: 12px; font-weight: bold; color: #CCCCCC;")
        card_layout.addWidget(lbl_email)

        self.email_entry = QLineEdit()
        self.email_entry.setPlaceholderText("duocsi@nhathuoc.com")
        self.email_entry.setFixedHeight(38)
        self.email_entry.returnPressed.connect(self.handle_login)
        card_layout.addWidget(self.email_entry)

        # Input Password
        lbl_pass = QLabel("Mật khẩu:")
        lbl_pass.setStyleSheet("font-size: 12px; font-weight: bold; color: #CCCCCC;")
        card_layout.addWidget(lbl_pass)

        self.pass_entry = QLineEdit()
        self.pass_entry.setPlaceholderText("••••••••")
        self.pass_entry.setEchoMode(QLineEdit.Password)
        self.pass_entry.setFixedHeight(38)
        self.pass_entry.returnPressed.connect(self.handle_login)
        card_layout.addWidget(self.pass_entry)

        # Label báo lỗi
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #FF5252; font-size: 12px;")
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.error_label)

        # Nút Đăng nhập
        self.login_btn = QPushButton("ĐĂNG NHẬP VÀO CA")
        self.login_btn.setFixedHeight(42)
        self.login_btn.setProperty("class", "PrimaryBtn")
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #1F6AA5;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #257EC4; }
            QPushButton:disabled { background-color: #4A4A4A; color: #888888; }
        """)
        self.login_btn.clicked.connect(self.handle_login)
        card_layout.addWidget(self.login_btn)

        main_layout.addWidget(self.card)

    def handle_login(self):
        email = self.email_entry.text().strip()
        password = self.pass_entry.text()

        if not email or not password:
            self.error_label.setText("Vui lòng nhập đầy đủ Email và Mật khẩu!")
            return

        if "@" not in email:
            email = f"{email}@nhathuoc.com"

        self.error_label.setStyleSheet("color: gray; font-size: 12px;")
        self.error_label.setText("Đang xác thực tài khoản...")
        self.login_btn.setEnabled(False)
        self.login_btn.setText("ĐANG XỬ LÝ...")

        # Chạy xác thực trong luồng QtWorker nền
        def auth_task():
            res = self.supabase.login(email, password)
            if not res.get("success"):
                return {"success": False, "message": res.get("message", "Đăng nhập thất bại")}

            profile = res.get("profile")
            user_role = profile.get("role")
            branch_id = profile.get("branch_id")

            if user_role in ("staff", "storemanager") and branch_id:
                is_allowed = self.supabase.check_device_permission(branch_id, self.device_uuid)
                if not is_allowed:
                    self.supabase.logout()
                    return {
                        "success": False,
                        "message": "Máy tính này chưa được đăng ký làm việc tại Chi nhánh của bạn! Vui lòng liên hệ Admin."
                    }
            return {"success": True, "profile": profile}

        self.worker = QtWorker(auth_task)
        self.worker.result_ready.connect(self._on_auth_finished)
        self.worker.error_occurred.connect(self._on_auth_error)
        self.worker.start()

    def _on_auth_finished(self, result):
        self.login_btn.setEnabled(True)
        self.login_btn.setText("ĐĂNG NHẬP VÀO CA")

        if result.get("success"):
            self.error_label.setText("")
            self.login_success.emit(result["profile"])
        else:
            self.error_label.setStyleSheet("color: #FF5252; font-size: 12px;")
            self.error_label.setText(result.get("message", "Đăng nhập thất bại!"))

    def _on_auth_error(self, err_msg):
        self.login_btn.setEnabled(True)
        self.login_btn.setText("ĐĂNG NHẬP VÀO CA")
        self.error_label.setStyleSheet("color: #FF5252; font-size: 12px;")
        self.error_label.setText(f"Lỗi kết nối: {err_msg}")
