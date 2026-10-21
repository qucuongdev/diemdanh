"""Admin editing of private HR fields and effective-dated salary terms."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QWidget, QScrollArea, QTabWidget, QComboBox,
)
from core.domain import local_now, display_duration
from core.ui_messages import UserInputError, public_error_message
from core.personnel import PERSONAL_FIELDS, TERM_FIELDS, validate_personal, validate_terms, display_money
from core.qt_worker import TaskRunner
from core.supabase_service import SupabaseService
from views_qt.common import button, label


def fields_panel(definitions):
    content = QWidget()
    form = QFormLayout(content)
    fields = {}
    for key, caption in definitions:
        fields[key] = QLineEdit()
        fields[key].setMaxLength(1000)
        form.addRow(caption, fields[key])
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    return scroll, fields


class EmployeeDialog(QDialog):
    changed = Signal()

    def __init__(self, parent, profile, employee, month):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Hồ sơ và chế độ lương · " + employee["full_name"])
        self.resize(740, 720)
        self.user_id = employee["user_id"]
        self.month = month
        self.profile = profile
        self.service = SupabaseService()
        self.tasks = TaskRunner(self)
        self.busy = False
        self.details = {}
        self.terms = []
        root = QVBoxLayout(self)
        root.addWidget(label(employee["full_name"], True))
        root.addWidget(label("Họ tên, điện thoại, chi nhánh và tài khoản được sửa tại Quản trị → Nhân sự."))
        self.tabs = QTabWidget()
        personal, self.personal_fields = fields_panel(PERSONAL_FIELDS)
        self.tabs.addTab(personal, "Thông tin cá nhân")
        pay = QWidget()
        pay_layout = QVBoxLayout(pay)
        self.term_choice = QComboBox()
        pay_layout.addWidget(self.term_choice)
        pay_layout.addWidget(label("Chế độ có hiệu lực từ đầu tháng. Tháng đã chốt được giữ nguyên. "
                                   "Cho phép 2 lần muộn: lần thứ 3 mất thưởng. Vắng/thiếu công ngoài phần muộn mất thưởng."))
        terms_panel, self.term_fields = fields_panel(TERM_FIELDS)
        pay_layout.addWidget(terms_panel)
        self.tabs.addTab(pay, "Lương và chuyên cần")
        root.addWidget(self.tabs, 1)
        self.message = label()
        root.addWidget(self.message)
        self.save_button = button("Lưu thông tin cá nhân", self.save_personal, True)
        self.pay_button = button("Lưu chế độ lương", self.save_terms, True)
        root.addWidget(self.save_button)
        root.addWidget(self.pay_button)
        root.addWidget(button("Đóng", self.close))
        self.term_choice.currentIndexChanged.connect(self.choose_term)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tab_changed()
        self.load()

    def tab_changed(self, *_):
        self.save_button.setVisible(self.tabs.currentIndex() == 0)
        self.pay_button.setVisible(self.tabs.currentIndex() == 1)

    def set_busy(self, busy):
        self.busy = busy
        self.tabs.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        self.pay_button.setEnabled(not busy)

    def load(self):
        if self.profile.get("role") != "admin":
            self.message.setText("Chỉ admin được xem hồ sơ này.")
            self.set_busy(True)
            return
        self.set_busy(True)
        self.tasks.submit("load", lambda: self.service.get_employee_private(self.user_id), self.loaded, self.load_failed)

    def loaded(self, result):
        self.set_busy(False)
        if not result.get("success"):
            self.load_failed(result.get("message"))
            return
        data = result.get("data") or {}
        self.details = data.get("details") or {}
        values = {**(self.details.get("details") or {}), **self.details}
        for key, widget in self.personal_fields.items():
            widget.setText(str(values.get(key) if values.get(key) is not None else (7 if key == "birthday_notice_days" else "")))
        self.terms = data.get("terms") or []
        self.term_choice.blockSignals(True)
        self.term_choice.clear()
        self.term_choice.addItem("Thêm chế độ từ tháng khác", None)
        for term in self.terms:
            self.term_choice.addItem(f"Từ {term['effective_month']} · {display_money(term['monthly_salary'])}", term)
        index = next((i + 1 for i, term in enumerate(self.terms) if term["effective_month"] == self.month), 0)
        self.term_choice.setCurrentIndex(index)
        self.term_choice.blockSignals(False)
        self.choose_term()

    def choose_term(self, *_):
        values = self.term_choice.currentData() or {
            "effective_month": self.month, "monthly_salary": "0", "paid_rest_days": "4",
            "daily_minutes": "480", "attendance_bonus": "0", "allowed_late_count": "0"}
        for key, widget in self.term_fields.items():
            widget.setText(display_duration(int(values[key])) if key == "daily_minutes" else str(values.get(key, "")))

    def failed(self, message):
        self.set_busy(False)
        self.message.setText(public_error_message(message))

    def load_failed(self, message):
        self.failed(message)
        self.tabs.setEnabled(False)
        self.save_button.setEnabled(False)
        self.pay_button.setEnabled(False)

    def save(self, work):
        if self.busy or self.profile.get("role") != "admin":
            return
        self.set_busy(True)

        def done(result):
            self.set_busy(False)
            if not result.get("success"):
                self.message.setText(public_error_message(result.get("message")))
                return
            self.message.setText("Đã lưu thay đổi.")
            self.changed.emit()
            self.load()

        self.tasks.submit("save", work, done, self.failed, replace=False)

    def save_personal(self):
        values = {key: widget.text().strip() for key, widget in self.personal_fields.items()}
        try:
            validate_personal(values, local_now().date())
        except UserInputError as exc:
            self.message.setText(public_error_message(exc))
            return
        revision = self.details.get("revision", 0)
        self.save(lambda: self.service.save_employee_private(self.user_id, values, revision))

    def save_terms(self):
        values = {key: widget.text().strip() for key, widget in self.term_fields.items()}
        try:
            month, terms = validate_terms(values)
        except UserInputError as exc:
            self.message.setText(public_error_message(exc))
            return
        revision = next((term["revision"] for term in self.terms if term["effective_month"] == month), 0)
        self.save(lambda: self.service.save_pay_terms(self.user_id, month, terms, revision))

    def closeEvent(self, event):
        if "save" in self.tasks._active:
            self.message.setText("Đang lưu, vui lòng chờ.")
            event.ignore()
            return
        self.tasks.invalidate()
        super().closeEvent(event)
