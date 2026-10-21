from pathlib import Path
from PySide6.QtWidgets import QHBoxLayout, QComboBox, QFileDialog
from core.domain import local_now, display_duration
from core.reports import summarize, export_attendance
from views_qt.common import Page, TableModel, table_for, button, label


class ReportView(Page):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent, current_profile)
        self.report_data = []
        self.report_title = ""
        self.export_busy = False
        self.heading(
            "Báo cáo chấm công", "Tổng hợp theo tháng · Ca chưa chấm công được tách khỏi ca đúng giờ."
        )
        controls = QHBoxLayout()
        self.branch_combo, self.month_combo, self.year_combo = QComboBox(), QComboBox(), QComboBox()
        self.branch_combo.setMinimumWidth(240)
        self.month_combo.setMinimumWidth(130)
        self.year_combo.setMinimumWidth(95)
        now = local_now()
        for month in range(1, 13):
            self.month_combo.addItem(f"Tháng {month}", month)
        self.month_combo.setCurrentIndex(now.month - 1)
        for year in range(now.year - 5, now.year + 2):
            self.year_combo.addItem(str(year), year)
        self.year_combo.setCurrentText(str(now.year))
        for combo in [self.branch_combo, self.month_combo, self.year_combo]:
            controls.addWidget(combo)
            combo.currentIndexChanged.connect(self.filters_changed)
        self.search_btn = button("Tra cứu", self.load_report_data, True)
        self.export_btn = button("Xuất Excel", self.export_to_excel)
        self.search_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        controls.addWidget(self.search_btn)
        controls.addStretch()
        controls.addWidget(self.export_btn)
        self.root.addLayout(controls)
        self.summary = label("Chọn kỳ báo cáo và bấm Tra cứu.")
        self.root.addWidget(self.summary)
        self.model = TableModel(
            [
                ("Nhân viên", lambda r: r["name"]),
                ("Tổng ca", lambda r: r["total"]),
                ("Đúng giờ", lambda r: r["ontime"]),
                ("Muộn", lambda r: r["late"]),
                ("Thời gian muộn", lambda r: display_duration(r["late_minutes"])),
                ("Nghỉ phép", lambda r: r["leave"]),
                ("Chưa ghi nhận", lambda r: r["unrecorded"]),
            ],
            self,
        )
        self.table = table_for(self.model)
        self.root.addWidget(self.table, 1)
        self.root.addWidget(self.status)
        self.tasks.submit("metadata", self.supabase.get_branches, self.metadata, self.error)

    def on_show(self):
        self.filters_changed()

    def metadata(self, branches):
        for branch in branches:
            if self.current_profile["role"] == "admin" or branch["id"] == self.current_profile["branch_id"]:
                self.branch_combo.addItem(branch["name"], branch["id"])
        self.branch_combo.setEnabled(self.current_profile["role"] == "admin")
        self.search_btn.setEnabled(self.branch_combo.count() > 0)

    def filters_changed(self, *_):
        self.tasks.cancel("report")
        self.report_data = []
        self.model.replace([])
        self.export_btn.setEnabled(False)
        self.summary.setText("Bấm Tra cứu để tải dữ liệu kỳ đã chọn.")
        self.status.clear()

    def load_report_data(self):
        branch = self.branch_combo.currentData()
        if not branch or self.current_profile["role"] not in ("admin", "storemanager"):
            self.error("Chọn chi nhánh hợp lệ để xem báo cáo.")
            return
        month, year = self.month_combo.currentData(), self.year_combo.currentData()
        title = f"{self.branch_combo.currentText()} · {month:02d}/{year}"
        self.status.setText("Đang tải toàn bộ dữ liệu kỳ báo cáo…")
        self.report_data = []
        self.model.replace([])
        self.summary.setText("Đang tổng hợp kỳ đã chọn…")
        self.export_btn.setEnabled(False)

        def fetch():
            records = self.supabase.get_monthly_attendance_data(branch, year, month)
            return records, summarize(records)

        def done(result):
            records, stats = result
            self.report_data = records
            self.report_title = title
            self.model.replace(stats)
            self.summary.setText(f"{title} · {len(records)} ca · {len(stats)} nhân viên")
            self.status.setText("" if records else "Không có dữ liệu trong kỳ này.")
            self.export_btn.setEnabled(bool(records) and not self.export_busy)

        def failed(message):
            self.summary.setText("Chưa tải được báo cáo. Bấm Tra cứu để thử lại.")
            self.error(message)

        self.tasks.submit("report", fetch, done, failed)

    def export_to_excel(self):
        if not self.report_data or not self.export_btn.isEnabled():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất báo cáo", "Bang_cham_cong.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        if Path(path).suffix.lower() != ".xlsx":
            path += ".xlsx"
        records, title = list(self.report_data), self.report_title
        self.export_busy = True
        self.export_btn.setEnabled(False)

        def done(saved):
            self.export_busy = False
            self.export_btn.setEnabled(bool(self.report_data))
            self.status.setText(f"Đã xuất báo cáo: {saved}")

        def failed(message):
            self.export_busy = False
            self.export_btn.setEnabled(bool(self.report_data))
            self.error(message)

        self.tasks.submit(
            "export", lambda: export_attendance(path, records, title), done, failed, replace=False
        )
