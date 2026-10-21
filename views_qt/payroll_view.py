"""Paginated admin payroll, private employee editing and daily payroll review."""

from datetime import date
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit, QMessageBox, QFileDialog, QPlainTextEdit
from core.domain import local_now, display_duration
from core.personnel import display_money, DAY_KINDS
from core.qt_worker import TaskRunner
from core.supabase_service import SupabaseService
from core.payroll_export import export_payroll
from core.ui_messages import public_error_message, public_payroll_warning
from views_qt.common import Page, TableModel, table_for, button, label, FormDialog
from views_qt.personnel_dialog import EmployeeDialog


class ReviewMessage(QPlainTextEdit):
    """Scrollable, plain-text feedback so many warnings cannot hide the ledger."""

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumHeight(110)

    def setText(self, text):
        self.setPlainText(text)

    def set_error(self, message):
        self.setPlainText(public_error_message(message))


class BirthdayDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Sinh nhật sắp tới")
        self.resize(760, 500)
        self.tasks = TaskRunner(self)
        self.service = SupabaseService()
        self.offset = 0
        root = QVBoxLayout(self)
        root.addWidget(label("Nhắc theo số ngày đã đặt trong hồ sơ · Ngày sinh 29/02 nhắc 28/02 ở năm thường."))
        self.model = TableModel([
            ("Họ tên", lambda r: r["full_name"]), ("Ngày sinh", lambda r: r["birth_date"]),
            ("Tuổi sắp tới", lambda r: r["age"]),
            ("Sinh nhật", lambda r: "Hôm nay" if r["days_until"] == 0 else f"Còn {r['days_until']} ngày"),
        ], self)
        root.addWidget(table_for(self.model), 1)
        self.message = label()
        root.addWidget(self.message)
        footer = QHBoxLayout()
        self.prev = button("Trang trước", lambda: self.move(-1))
        self.next = button("Trang sau", lambda: self.move(1))
        footer.addWidget(self.prev)
        footer.addWidget(self.next)
        footer.addWidget(button("Đóng", self.close))
        root.addLayout(footer)
        self.load()

    def move(self, direction):
        self.offset = max(0, self.offset + direction * 50)
        self.load()

    def load(self):
        self.model.replace([])
        self.prev.setEnabled(False)
        self.next.setEnabled(False)
        offset = self.offset
        self.tasks.submit("birthdays", lambda: self.service.get_upcoming_birthdays(offset, 51),
                          self.loaded, self.failed)

    def failed(self, message):
        self.message.setText(public_error_message(message))
        self.prev.setEnabled(self.offset > 0)

    def loaded(self, result):
        if not result.get("success"):
            self.failed(result.get("message"))
            return
        rows = result.get("data") or []
        self.model.replace(rows[:50])
        self.message.setText("Không có sinh nhật trong khoảng nhắc." if not rows else f"Trang {self.offset // 50 + 1}")
        self.prev.setEnabled(self.offset > 0)
        self.next.setEnabled(len(rows) > 50)

    def closeEvent(self, event):
        self.tasks.invalidate()
        super().closeEvent(event)


class PayrollDetailDialog(QDialog):
    def __init__(self, parent, row, on_changed):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Chi tiết công và lương · " + row["full_name"])
        self.resize(1080, 730)
        self.tasks = TaskRunner(self)
        self.service = SupabaseService()
        self.user_id, self.month = row["user_id"], row["month"]
        self.result = None
        self.on_changed = on_changed
        root = QVBoxLayout(self)
        self.summary = label()
        root.addWidget(self.summary)
        self.model = TableModel([
            ("Ngày", lambda r: r["date"]), ("Loại ngày", lambda r: DAY_KINDS.get(r["kind"], r["kind"])),
            ("Đã xếp", lambda r: display_duration(r["planned_minutes"])),
            ("Giờ làm", lambda r: display_duration(r["worked_minutes"])),
            ("Muộn", lambda r: display_duration(r["late_minutes"])),
            ("Ghi chú", lambda r: r["note"]), ("Cảnh báo", lambda r: public_payroll_warning(r.get("warning", ""))),
        ], self)
        self.table = table_for(self.model)
        root.addWidget(self.table, 1)
        self.message = ReviewMessage()
        root.addWidget(self.message)
        footer = QHBoxLayout()
        self.edit_button = button("Phân loại ngày đã chọn", self.edit_day)
        self.final_button = button("Chốt lương tháng", self.finalize, True)
        self.reload_button = button("Tải lại", self.load)
        for control in (self.edit_button, self.final_button, self.reload_button):
            footer.addWidget(control)
        footer.addWidget(button("Đóng", self.close))
        root.addLayout(footer)
        self.load()

    def load(self):
        self.result = None
        self.model.replace([])
        self.edit_button.setEnabled(False)
        self.final_button.setEnabled(False)
        self.message.setText("Đang tính từ dữ liệu máy chủ…")
        self.tasks.submit("preview", lambda: self.service.get_payroll_preview(self.user_id, self.month),
                          self.loaded, self.message.set_error)

    def loaded(self, response):
        if not response.get("success"):
            self.message.set_error(response.get("message"))
            return
        self.result = response["data"]
        r = self.result
        self.model.replace(r.get("days") or [])
        state = "Đã chốt" if r.get("finalized") else "Tạm tính"
        self.summary.setText(
            f"{state} · {self.month[:7]} · Thực nhận {display_money(r.get('net_salary'))}\n"
            f"Lương kỳ {display_money(r.get('base_salary'))} · Trừ thiếu {display_money(r.get('deduction'))} · "
            f"Làm thêm {display_money(r.get('extra_pay'))} · Chuyên cần {display_money(r.get('bonus'))}\n"
            f"Công chuẩn {display_duration(r.get('expected_minutes'))} · "
            f"Thiếu {display_duration(r.get('missing_minutes'))} · Số lần muộn {r.get('late_count', '—')}"
        )
        warnings = r.get("warnings") or []
        self.message.setText("\n".join(public_payroll_warning(w) for w in warnings) if warnings else
                             ("Bảng lương đã chốt được lưu cố định." if r.get("finalized") else
                              "Chỉ chốt sau khi hết tháng và xử lý mọi cảnh báo."))
        self.edit_button.setEnabled(not r.get("finalized") and bool(r.get("days")))
        self.final_button.setEnabled(not r.get("finalized") and r.get("period_closed", False)
                                     and not warnings and r.get("net_salary") is not None)

    def edit_day(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows or not self.result or self.result.get("finalized"):
            return
        record = dict(self.model.records[rows[0].row()])
        if record["kind"] == "outside":
            self.message.setText("Ngày này ngoài thời gian làm việc của nhân viên.")
            return
        dialog = FormDialog(self, "Phân loại ngày " + record["date"], [
            ("kind", "Loại ngày", [(v, k) for k, v in DAY_KINDS.items() if k != "outside"]),
            ("note", "Lý do (bắt buộc)", record["note"]),
        ])
        dialog.fields["kind"].setCurrentIndex(dialog.fields["kind"].findData(record["kind"]))

        def save():
            values = dialog.values()
            if not values["note"] or len(values["note"]) > 1000:
                dialog.message.setText("Nhập lý do từ 1 đến 1.000 ký tự.")
                return
            dialog.save(lambda: self.service.set_payroll_day(self.user_id, record["date"],
                        values["kind"], values["note"], record["revision"]), self.day_saved)

        dialog.buttons.accepted.connect(save)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.open()

    def day_saved(self):
        self.on_changed()
        self.load()

    def finalize(self):
        if not self.result or not self.final_button.isEnabled():
            return
        if QMessageBox.question(self, "Chốt lương", "Lưu cố định bảng lương tháng này? Không thể sửa sau khi chốt.",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        signature = self.result["source_signature"]
        for control in (self.edit_button, self.final_button, self.reload_button):
            control.setEnabled(False)
        self.tasks.submit("finalize", lambda: self.service.finalize_payroll(self.user_id, self.month, signature),
                          self.finalized, self.final_failed, replace=False)

    def final_failed(self, message):
        self.reload_button.setEnabled(True)
        self.message.setText(public_error_message(message) + " Tải lại để kiểm tra trước khi thử lại.")

    def finalized(self, response):
        self.reload_button.setEnabled(True)
        if not response.get("success"):
            self.final_failed(response.get("message", "Không thể chốt."))
            return
        self.day_saved()

    def closeEvent(self, event):
        if "finalize" in self.tasks._active or any(d.tasks._active for d in self.findChildren(FormDialog)):
            self.message.setText("Đang lưu, vui lòng chờ.")
            event.ignore()
            return
        self.tasks.invalidate()
        super().closeEvent(event)


class PayrollView(Page):
    PAGE_SIZE = 20

    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent, current_profile)
        self.offset = 0
        self.export_busy = False
        self.loaded_filters = None
        self.heading("Nhân sự và bảng lương", "Chỉ admin · Lương theo công thực tế trong ca · Bảng đang xem có phân trang.")
        filters = QHBoxLayout()
        now = local_now()
        self.month = QComboBox()
        self.year = QComboBox()
        self.branch = QComboBox()
        self.month.setMinimumWidth(120)
        self.year.setMinimumWidth(95)
        self.branch.setMinimumWidth(200)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm tên nhân viên")
        for value in range(1, 13):
            self.month.addItem(f"Tháng {value}", value)
        self.month.setCurrentIndex(now.month - 1)
        for value in range(now.year - 10, now.year + 3):
            self.year.addItem(str(value), value)
        self.year.setCurrentText(str(now.year))
        self.branch.addItem("Tất cả chi nhánh", None)
        for control in (self.month, self.year, self.branch, self.search):
            filters.addWidget(control)
        self.load_button = button("Tra cứu", self.reset, True)
        filters.addWidget(self.load_button)
        self.root.addLayout(filters)
        self.model = TableModel([
            ("Họ tên", lambda r: r["full_name"]), ("Chi nhánh", lambda r: r.get("branch_name")),
            ("Lương tháng", lambda r: display_money(r.get("monthly_salary"))),
            ("Giờ làm", lambda r: display_duration((r.get("regular_minutes", 0) + r.get("extra_minutes", 0))
                                                 if r.get("net_salary") is not None else None)),
            ("Thiếu công", lambda r: display_duration(r.get("missing_minutes"))),
            ("Tiền trừ", lambda r: display_money(r.get("deduction"))),
            ("Làm thêm", lambda r: display_money(r.get("extra_pay"))),
            ("Chuyên cần", lambda r: display_money(r.get("bonus"))),
            ("Thực nhận", lambda r: display_money(r.get("net_salary"))),
            ("Trạng thái", lambda r: "Đã chốt" if r.get("finalized") else
             ("Cần kiểm tra" if r.get("warnings") else "Tạm tính"),
             lambda r: "\n".join(public_payroll_warning(w) for w in (r.get("warnings") or []))),
        ], self)
        self.table = table_for(self.model)
        self.root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.employee_button = button("Thông tin nhân sự / lương", self.employee)
        self.detail_button = button("Chi tiết công / chốt lương", self.detail)
        self.export_button = button("Xuất Excel toàn bộ bộ lọc", self.export)
        for control in (self.employee_button, self.detail_button, self.export_button):
            actions.addWidget(control)
        actions.addWidget(button("Sinh nhật sắp tới", self.birthdays))
        self.root.addLayout(actions)
        footer = QHBoxLayout()
        self.prev = button("Trang trước", lambda: self.move(-1))
        self.next = button("Trang sau", lambda: self.move(1))
        self.page_label = label()
        for control in (self.prev, self.page_label, self.next):
            footer.addWidget(control)
        self.root.addLayout(footer)
        self.root.addWidget(self.status)
        for control in (self.month, self.year, self.branch):
            control.currentIndexChanged.connect(self.reset)
        self.search.returnPressed.connect(self.reset)
        self.search.textChanged.connect(self.invalidate_filters)
        self.table.selectionModel().selectionChanged.connect(self.selection_changed)
        self.tasks.submit("branches", self.supabase.get_branches, self.branches_loaded, self.error)
        self.load()

    def filters(self):
        return date(self.year.currentData(), self.month.currentData(), 1).isoformat(), self.search.text().strip(), self.branch.currentData()

    def branches_loaded(self, branches):
        self.branch.blockSignals(True)
        for item in branches:
            self.branch.addItem(item["name"], item["id"])
        self.branch.blockSignals(False)

    def invalidate_filters(self, *_):
        self.tasks.cancel("payroll")
        self.loaded_filters = None
        self.model.replace([])
        self.prev.setEnabled(False)
        self.next.setEnabled(False)
        self.export_button.setEnabled(False)
        self.selection_changed()

    def on_show(self):
        self.load()

    def on_hide(self):
        self.invalidate_filters()

    def reset(self, *_):
        self.offset = 0
        self.load()

    def move(self, direction):
        self.offset = max(0, self.offset + direction * self.PAGE_SIZE)
        self.load()

    def load(self):
        self.invalidate_filters()
        if self.current_profile.get("role") != "admin":
            self.error("Chỉ admin được xem nhân sự và bảng lương.")
            return
        month, search, branch = self.filters()
        offset = self.offset
        self.status.setText("Đang tính lương trên máy chủ…")

        def loaded(response):
            if not response.get("success"):
                self.error(response.get("message", "Không thể tải lương."))
                self.prev.setEnabled(offset > 0)
                return
            rows = response.get("data") or []
            self.loaded_filters = (month, search, branch)
            self.model.replace(rows[:self.PAGE_SIZE])
            self.prev.setEnabled(offset > 0)
            self.next.setEnabled(len(rows) > self.PAGE_SIZE)
            self.export_button.setEnabled(not self.export_busy)
            self.page_label.setText(f"Trang {offset // self.PAGE_SIZE + 1}")
            self.status.setText(f"{len(rows[:self.PAGE_SIZE])} nhân viên trên trang · "
                                "Tạm tính chưa phải bảng lương đã chốt. Chọn nhân viên để xem cảnh báo và công từng ngày.")

        self.tasks.submit("payroll", lambda: self.supabase.get_payroll_page(month, offset, self.PAGE_SIZE + 1,
                          search, branch), loaded, self.error)

    def selection_changed(self, *_):
        selected = bool(self.selected(self.table)) and self.loaded_filters is not None
        self.employee_button.setEnabled(selected)
        self.detail_button.setEnabled(selected)

    def employee(self):
        row = self.selected(self.table)
        if row and self.loaded_filters:
            dialog = EmployeeDialog(self, self.current_profile, row, row["month"])
            dialog.changed.connect(self.load)
            dialog.open()

    def detail(self):
        row = self.selected(self.table)
        if row and self.loaded_filters:
            PayrollDetailDialog(self, row, self.load).open()

    def birthdays(self):
        BirthdayDialog(self).open()

    def export(self):
        if self.export_busy or self.loaded_filters is None:
            return
        filters = self.loaded_filters
        path, _ = QFileDialog.getSaveFileName(self, "Xuất bảng lương", f"bang_luong_{filters[0][:7]}.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        self.export_busy = True
        self.export_button.setEnabled(False)

        def work():
            month, search, branch = filters
            records, offset = [], 0
            while True:
                response = self.supabase.get_payroll_page(month, offset, 50, search, branch)
                if not response.get("success"):
                    return response
                rows = response.get("data") or []
                records.extend(rows)
                if len(rows) < 50:
                    break
                offset += len(rows)
            export_payroll(path, records, month)
            return {"success": True}

        def done(response):
            self.export_busy = False
            self.export_button.setEnabled(self.loaded_filters is not None)
            if response.get("success"):
                self.status.setText("Đã xuất toàn bộ nhân viên theo bộ lọc đã chọn; file có ghi trạng thái chốt/tạm tính.")
            else:
                self.error(response.get("message", "Không thể xuất bảng lương."))

        def failed(message):
            self.export_busy = False
            self.export_button.setEnabled(self.loaded_filters is not None)
            self.error(message)

        self.tasks.submit("export", work, done, failed, replace=False)
