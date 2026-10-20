import calendar
from datetime import date
from PySide6.QtCore import QDate, Qt, Slot
from PySide6.QtGui import QTextCharFormat, QColor, QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QComboBox, QCalendarWidget, QMessageBox, QToolButton
from core.domain import local_now, first_attendance
from views_qt.common import Page, TableModel, table_for, button, FormDialog


class ScheduleView(Page):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent, current_profile)
        self.ready = False
        self.loading = False
        self.branches, self.staffs, self.shifts = [], [], []
        self.schedules = []
        self._marked_dates = []
        self.heading(
            "Lịch làm việc",
            "Chọn ngày trên lịch để xem ca. Bảng hỗ trợ nhiều nhân viên và nhiều ca mỗi ngày.",
        )
        controls = QHBoxLayout()
        self.branch_combo, self.staff_combo = QComboBox(), QComboBox()
        controls.addWidget(self.branch_combo, 1)
        controls.addWidget(self.staff_combo, 1)
        controls.addWidget(button("Hôm nay", self.goto_today))
        controls.addWidget(button("Làm mới", self.refresh_calendar))
        self.add_btn = button("Xếp ca", self.open_add_schedule_modal, True)
        controls.addWidget(self.add_btn)
        controls.addWidget(button("Xin nghỉ", self.open_general_leave_modal))
        self.root.addLayout(controls)
        body = QHBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(False)
        self.calendar.setMinimumWidth(320)
        self.calendar.setMaximumWidth(450)
        self.calendar.setMinimumHeight(320)
        self.calendar.setMaximumHeight(360)
        self.calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        today = local_now().date()
        self.calendar.setSelectedDate(QDate(today.year, today.month, today.day))
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        body.addWidget(self.calendar, 1, Qt.AlignmentFlag.AlignTop)
        self.model = TableModel(
            [
                ("Nhân viên", lambda r: (r.get("profiles") or {}).get("full_name")),
                ("Ca làm", lambda r: (r.get("shifts") or {}).get("name")),
                ("Bắt đầu", lambda r: str((r.get("shifts") or {}).get("start_time", ""))[:5]),
                ("Kết thúc", lambda r: str((r.get("shifts") or {}).get("end_time", ""))[:5]),
                (
                    "Trạng thái",
                    lambda r: {
                        "scheduled": "Đã xếp ca",
                        "completed": "Hoàn thành",
                        "leave": "Đã duyệt nghỉ",
                        "absent": "Vắng mặt",
                    }.get(r.get("status"), "Không rõ"),
                ),
            ],
            self,
        )
        self.table = table_for(self.model)
        body.addWidget(self.table, 2)
        self.root.addLayout(body, 1)
        footer = QHBoxLayout()
        footer.addWidget(button("Lịch sử ngày này", self.open_attendance_history_modal))
        self.delete_btn = button("Xóa ca đã chọn", self.delete_schedule)
        footer.addWidget(self.delete_btn)
        footer.addStretch()
        self.root.addLayout(footer)
        self.root.addWidget(self.status)
        manager = self.current_profile["role"] in ("admin", "storemanager")
        self.add_btn.setVisible(manager)
        self.delete_btn.setVisible(manager)
        self.calendar.currentPageChanged.connect(self.render_month_calendar)
        self.calendar.selectionChanged.connect(self.render_selected_day)
        self.branch_combo.currentIndexChanged.connect(self.render_month_calendar)
        self.staff_combo.currentIndexChanged.connect(self.render_month_calendar)
        self.theme_manager = QApplication.instance().theme_manager
        self.theme_manager.changed.connect(self.apply_calendar_theme)
        self.apply_calendar_theme()
        self.refresh_calendar()

    @Slot(str)
    def apply_calendar_theme(self, _mode=None):
        colors = self.theme_manager.colors
        # Text arrows inherit both palettes; Qt's cached navigation icons can stay black.
        for name, text, caption in (("qt_calendar_prevmonth", "‹", "Tháng trước"),
                                    ("qt_calendar_nextmonth", "›", "Tháng sau")):
            navigation = self.calendar.findChild(QToolButton, name)
            if navigation is not None:
                navigation.setIcon(QIcon())
                navigation.setArrowType(Qt.ArrowType.NoArrow)
                navigation.setText(text)
                navigation.setAccessibleName(caption)
        weekend = QTextCharFormat()
        weekend.setForeground(QColor(colors["weekend"]))
        for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.calendar.setWeekdayTextFormat(day, weekend)
        marked = QTextCharFormat()
        marked.setBackground(QColor(colors["selection"]))
        marked.setForeground(QColor(colors["selection_text"]))
        for day in self._marked_dates:
            self.calendar.setDateTextFormat(day, marked)

    def goto_today(self):
        today = local_now().date()
        self.calendar.setSelectedDate(QDate(today.year, today.month, today.day))
        self.calendar.showSelectedDate()
        self.render_month_calendar()

    def on_show(self):
        if self.ready:
            self.refresh_calendar()

    def refresh_calendar(self):
        self.ready = False
        self.tasks.cancel("calendar")
        self.loading = True
        for day in self._marked_dates:
            self.calendar.setDateTextFormat(day, QTextCharFormat())
        self._marked_dates = []
        self.schedules = []
        self.model.replace([])
        self.delete_btn.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.status.setText("Đang tải danh mục…")
        self.tasks.submit(
            "metadata",
            lambda: (
                self.supabase.get_branches(True),
                self.supabase.get_staff_list(force_refresh=True),
                self.supabase.get_shifts(force_refresh=True),
            ),
            self.metadata,
            self.metadata_failed,
        )

    def metadata_failed(self, message):
        self.loading = False
        self.error(message)

    def metadata(self, result):
        self.branches, self.staffs, self.shifts = result
        old_branch, old_staff = self.branch_combo.currentData(), self.staff_combo.currentData()
        role = self.current_profile["role"]
        for combo in [self.branch_combo, self.staff_combo]:
            combo.blockSignals(True)
            combo.clear()
        if role == "admin":
            self.branch_combo.addItem("Tất cả chi nhánh", None)
        for item in self.branches:
            if role == "admin" or item["id"] == self.current_profile["branch_id"]:
                self.branch_combo.addItem(item["name"], item["id"])
        self.branch_combo.setEnabled(role == "admin")
        if role != "staff":
            self.staff_combo.addItem("Tất cả nhân viên", None)
            for item in self.staffs:
                if role == "admin" or item.get("branch_id") == self.current_profile["branch_id"]:
                    self.staff_combo.addItem(f"{item['full_name']} · {item['id'][:6]}", item["id"])
        else:
            self.staff_combo.addItem(self.current_profile.get("full_name", "Tôi"), self.current_profile["id"])
            self.staff_combo.setEnabled(False)
        for combo, previous in [(self.branch_combo, old_branch), (self.staff_combo, old_staff)]:
            index = combo.findData(previous)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self.ready = True
        self.add_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.render_month_calendar()

    def render_month_calendar(self, *_):
        if not self.ready:
            return
        year, month = self.calendar.yearShown(), self.calendar.monthShown()
        start = date(year, month, 1).isoformat()
        end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        role = self.current_profile["role"]
        branch = self.branch_combo.currentData() if role == "admin" else self.current_profile["branch_id"]
        user = self.current_profile["id"] if role == "staff" else self.staff_combo.currentData()
        self.status.setText("Đang tải lịch làm việc…")
        self.loading = True
        self.schedules = []
        for day in self._marked_dates:
            self.calendar.setDateTextFormat(day, QTextCharFormat())
        self._marked_dates = []
        self.render_selected_day()
        self.tasks.submit(
            "calendar",
            lambda: self.supabase.get_schedules_range(branch, user, start, end),
            self.loaded,
            self.calendar_failed,
        )

    def calendar_failed(self, message):
        self.loaded([])
        self.error(message)

    def loaded(self, records):
        self.loading = False
        self.schedules = records
        for day in self._marked_dates:
            self.calendar.setDateTextFormat(day, QTextCharFormat())
        self._marked_dates = []
        for value in {record.get("work_date") for record in records}:
            if value:
                day = QDate.fromString(value, "yyyy-MM-dd")
                self._marked_dates.append(day)
        self.apply_calendar_theme()
        self.render_selected_day()

    def render_selected_day(self):
        selected = self.calendar.selectedDate().toString("yyyy-MM-dd")
        records = [r for r in self.schedules if r.get("work_date") == selected]
        self.model.replace(records)
        if not self.loading:
            self.status.setText(
                f"Ngày {self.calendar.selectedDate().toString('dd/MM/yyyy')} · {len(records)} ca làm việc"
            )

    def open_attendance_history_modal(self):
        from views_qt.attendance_history_dialog import AttendanceHistoryDialog

        dialog = AttendanceHistoryDialog(
            self,
            self.current_profile,
            self.calendar.selectedDate().toString("yyyy-MM-dd"),
            self.staff_combo.currentData(),
        )
        dialog.open()

    def open_add_schedule_modal(self):
        if not self.ready or self.current_profile["role"] not in ("admin", "storemanager"):
            return
        branches = [
            b
            for b in self.branches
            if self.current_profile["role"] == "admin" or b["id"] == self.current_profile["branch_id"]
        ]
        dialog = FormDialog(
            self,
            "Xếp ca làm việc",
            [
                ("branch", "Chi nhánh", [(b["name"], b["id"]) for b in branches]),
                ("staff", "Nhân viên", []),
                ("shift", "Ca làm", []),
                ("date", "Ngày YYYY-MM-DD", self.calendar.selectedDate().toString("yyyy-MM-dd")),
            ],
        )

        def update_choices():
            branch = dialog.fields["branch"].currentData()
            for key, items, caption in [("staff", self.staffs, "full_name"), ("shift", self.shifts, "name")]:
                combo = dialog.fields[key]
                combo.clear()
                for item in items:
                    if item.get("branch_id") == branch and item.get("is_active", True):
                        combo.addItem(f"{item[caption]} · {item['id'][:6]}", item["id"])

        dialog.fields["branch"].currentIndexChanged.connect(update_choices)
        update_choices()

        def save():
            values = dialog.values()
            try:
                date.fromisoformat(values["date"])
                if not all(values.values()):
                    raise ValueError()
            except ValueError:
                dialog.message.setText("Chọn chi nhánh, nhân viên, ca và nhập ngày hợp lệ.")
                return
            dialog.save(
                lambda: self.supabase.create_schedule(
                    values["branch"], values["staff"], values["shift"], values["date"]
                ),
                self.render_month_calendar,
            )

        dialog.buttons.accepted.connect(save)
        dialog.exec()
        dialog.deleteLater()

    def open_general_leave_modal(self):
        # Select the exact schedule, rather than silently using the first shift.
        user_id = self.current_profile["id"]
        records = [
            r
            for r in self.model.records
            if r.get("user_id") == user_id and r.get("status") == "scheduled" and not first_attendance(r)
        ]
        if not records:
            self.error("Chọn ngày có ca của bạn chưa chấm công để xin nghỉ.")
            return
        dialog = FormDialog(
            self,
            "Xin nghỉ phép",
            [
                (
                    "schedule",
                    "Ca xin nghỉ",
                    [((r.get("shifts") or {}).get("name", "Ca làm"), r["id"]) for r in records],
                ),
                (
                    "type",
                    "Loại nghỉ",
                    [
                        ("Nghỉ ốm", "sick"),
                        ("Phép năm", "annual"),
                        ("Việc riêng", "unpaid"),
                        ("Đổi ca", "swap"),
                    ],
                ),
                ("reason", "Lý do", ""),
            ],
        )

        def save():
            values = dialog.values()
            if not values["reason"]:
                dialog.message.setText("Nhập lý do xin nghỉ.")
                return
            record = next(r for r in records if r["id"] == values["schedule"])
            dialog.save(
                lambda: self.supabase.submit_leave_request(
                    record["id"], record["branch_id"], values["type"], values["reason"]
                ),
                lambda: self.status.setText("Đã gửi đơn xin nghỉ."),
            )

        dialog.buttons.accepted.connect(save)
        dialog.exec()
        dialog.deleteLater()

    def delete_schedule(self):
        record = self.selected(self.table)
        if not record or self.current_profile["role"] not in ("admin", "storemanager"):
            return
        if first_attendance(record):
            self.error("Không thể xóa ca đã có dữ liệu chấm công.")
            return
        if (
            QMessageBox.question(
                self, "Xóa ca", "Xóa ca làm việc đã chọn?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            == QMessageBox.Yes
        ):
            record_id = record["id"]
            self.mutate(
                lambda: self.supabase.delete_schedule(record_id),
                self.render_month_calendar,
                [self.delete_btn],
            )
