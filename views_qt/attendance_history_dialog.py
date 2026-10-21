from datetime import date
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit
from core.domain import display_time, local_now, timestamp_tooltip, attendance_work_credit, display_duration
from views_qt.common import Page, TableModel, table_for, button, label


def history_status(record):
    credit = attendance_work_credit(record)
    return f"● {credit.status}" if credit.minutes is not None else credit.status


class HistoryTableModel(TableModel):
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and index.column() == self.columnCount() - 1 and role == Qt.ItemDataRole.ForegroundRole:
            credit = attendance_work_credit(self.records[index.row()])
            if credit.minutes is not None:
                colors = QApplication.instance().theme_manager.colors
                return QColor(colors["success" if credit.missing_minutes == 0 else "error"])
        return super().data(index, role)


class HistoryPage(Page):
    PAGE_SIZE = 50

    def __init__(self, parent, profile, target_date, target_user_id):
        super().__init__(parent, profile)
        self.offset = 0
        self.ready = False
        self.target_user_id = target_user_id
        self.heading("Lịch sử chấm công", "Giờ làm chỉ tính trong khung ca · Thống kê áp dụng cho trang đang xem.")
        filters = QHBoxLayout()
        self.date_entry = QLineEdit(str(target_date or ""))
        self.date_entry.setPlaceholderText("Ngày YYYY-MM-DD hoặc để trống")
        self.staff_combo = QComboBox()
        self.branch_combo = QComboBox()
        filters.addWidget(self.date_entry, 1)
        filters.addWidget(button("Hôm nay", self.today))
        filters.addWidget(self.staff_combo, 1)
        filters.addWidget(self.branch_combo, 1)
        filters.addWidget(button("Tra cứu", self.reset, True))
        self.root.addLayout(filters)
        self.summary = label()
        self.root.addWidget(self.summary)
        self.model = HistoryTableModel(
            [
                ("Nhân viên", lambda r: (r.get("profiles") or {}).get("full_name")),
                ("Chi nhánh", lambda r: (r.get("branches") or {}).get("name")),
                ("Ngày", lambda r: (r.get("schedules") or {}).get("work_date")),
                ("Ca", lambda r: ((r.get("schedules") or {}).get("shifts") or {}).get("name")),
                ("Check-in", lambda r: display_time(r.get("check_in")),
                 lambda r: timestamp_tooltip(r.get("check_in"))),
                ("Check-out", lambda r: display_time(r.get("check_out")),
                 lambda r: timestamp_tooltip(r.get("check_out"))),
                ("Giờ làm", lambda r: display_duration(attendance_work_credit(r).minutes),
                 lambda r: "Chỉ tính thời gian trong ca; phút làm tròn xuống, phút thiếu làm tròn lên."
                 " Chưa trừ nghỉ giữa ca."),
                ("Trạng thái", history_status),
            ],
            self,
        )
        self.table = table_for(self.model)
        QApplication.instance().theme_manager.changed.connect(self.table.viewport().update)
        self.root.addWidget(self.table, 1)
        self.root.addWidget(self.status)
        footer = QHBoxLayout()
        self.prev_btn = button("Trang trước", lambda: self.move(-1))
        self.next_btn = button("Trang sau", lambda: self.move(1))
        self.page_label = label("Trang 1")
        footer.addWidget(self.prev_btn)
        footer.addWidget(self.page_label)
        footer.addStretch()
        footer.addWidget(self.next_btn)
        self.root.addLayout(footer)
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.tasks.submit(
            "metadata",
            lambda: (self.supabase.get_branches(), self.supabase.get_staff_list()),
            self.metadata,
            self.error,
        )
        self.date_entry.returnPressed.connect(self.reset)

    def metadata(self, result):
        branches, staff = result
        role = self.current_profile["role"]
        self.branch_combo.addItem("Tất cả chi nhánh", None)
        for item in branches:
            if role == "admin" or item["id"] == self.current_profile.get("branch_id"):
                self.branch_combo.addItem(item["name"], item["id"])
        self.staff_combo.addItem("Tất cả nhân viên", None)
        for item in staff:
            self.staff_combo.addItem(f"{item['full_name']} · {item['id'][:6]}", item["id"])
        if role == "staff":
            self.staff_combo.clear()
            self.staff_combo.addItem(self.current_profile.get("full_name", "Tôi"), self.current_profile["id"])
            self.staff_combo.setEnabled(False)
        if role != "admin":
            index = self.branch_combo.findData(self.current_profile.get("branch_id"))
            self.branch_combo.setCurrentIndex(max(0, index))
            self.branch_combo.setEnabled(False)
        index = self.staff_combo.findData(self.target_user_id)
        if self.target_user_id and index >= 0 and role != "staff":
            self.staff_combo.setCurrentIndex(index)
        self.ready = True
        self.staff_combo.currentIndexChanged.connect(self.reset)
        self.branch_combo.currentIndexChanged.connect(self.reset)
        self.load_data()

    def today(self):
        self.date_entry.setText(local_now().date().isoformat())
        self.reset()

    def reset(self, *_):
        self.offset = 0
        self.load_data()

    def move(self, direction):
        self.offset = max(0, self.offset + direction * self.PAGE_SIZE)
        self.load_data()

    def load_data(self):
        if not self.ready:
            return
        self.tasks.cancel("history")
        self.model.replace([])
        self.summary.clear()
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        raw = self.date_entry.text().strip()
        try:
            if raw:
                date.fromisoformat(raw)
        except ValueError:
            self.model.replace([])
            self.error("Ngày không hợp lệ. Dùng định dạng YYYY-MM-DD.")
            return
        profile = self.current_profile
        user_id = profile["id"] if profile["role"] == "staff" else self.staff_combo.currentData()
        branch_id = self.branch_combo.currentData() if profile["role"] == "admin" else profile["branch_id"]
        offset = self.offset
        self.status.setText("Đang tải lịch sử…")
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.tasks.submit(
            "history",
            lambda: self.supabase.get_attendance_history(
                branch_id, user_id, raw or None, self.PAGE_SIZE + 1, offset
            ),
            self._render_records,
            self.load_error,
        )

    def load_error(self, message):
        self.model.replace([])
        self.summary.clear()
        self.error(message)
        self.prev_btn.setEnabled(self.offset > 0)

    def _render_records(self, records):
        page = records[: self.PAGE_SIZE]
        self.model.replace(page)
        late = sum(bool(r.get("is_late")) for r in page)
        early = sum(bool(r.get("is_early_leave")) for r in page)
        self.summary.setText(f"Trang này: {len(page)} lượt · {late} lượt muộn · {early} lượt về sớm")
        self.status.setText("" if page else "Không có bản ghi phù hợp.")
        self.page_label.setText(f"Trang {self.offset // self.PAGE_SIZE + 1}")
        self.prev_btn.setEnabled(self.offset > 0)
        self.next_btn.setEnabled(len(records) > self.PAGE_SIZE)


class AttendanceHistoryDialog(QDialog):
    def __init__(self, parent=None, current_profile=None, target_date=None, target_user_id=None):
        super().__init__(parent)
        self.setWindowTitle("Lịch sử chấm công")
        self.resize(1100, 680)
        self.setMinimumSize(900, 550)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.page = HistoryPage(self, current_profile, target_date, target_user_id)
        layout.addWidget(self.page)

    def closeEvent(self, event):
        self.page.tasks.invalidate()
        super().closeEvent(event)
