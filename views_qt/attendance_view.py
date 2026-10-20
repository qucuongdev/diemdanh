from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QFrame, QComboBox, QFileDialog, QInputDialog, QWidget
from core.domain import local_now, first_attendance, display_time, attendance_notes, timestamp_tooltip
from core.hardware import get_hardware_uuid
from views_qt.common import Page, label, button


class AttendanceView(Page):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent, current_profile)
        outer = self.root
        panel = QWidget()
        panel.setMaximumWidth(1100)
        self.root = QVBoxLayout(panel)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(16)
        panel_row = QHBoxLayout()
        panel_row.addWidget(panel, 1)
        panel_row.addStretch()
        outer.addLayout(panel_row)
        outer.addStretch()
        self.schedules = []
        self.busy = False
        self.loading = False
        self._attendance_message = ""
        self.device_uuid = None
        self.heading(
            "Check-in / Check-out",
            f"Xin chào {self.current_profile.get('full_name', '')}. Chúc bạn một ca làm việc thuận lợi.",
        )
        actions = QHBoxLayout()
        actions.addWidget(button("Lịch sử chấm công", self.open_attendance_history_dialog))
        actions.addWidget(button("Làm mới", self.load_schedule))
        actions.addStretch()
        self.root.addLayout(actions)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(1100)
        content = QVBoxLayout(card)
        content.setContentsMargins(28, 28, 28, 28)
        content.setSpacing(20)
        self.clock_label = label(local_now().strftime("%H:%M"))
        self.clock_label.setObjectName("Clock")
        content.addWidget(self.clock_label)
        self.date_label = label(local_now().strftime("%d/%m/%Y") + " · Giờ Việt Nam")
        content.addWidget(self.date_label)
        content.addWidget(label("Ca làm việc"))
        self.shift_combo = QComboBox()
        self.shift_combo.currentIndexChanged.connect(self.apply_selection)
        content.addWidget(self.shift_combo)
        self.detail = label("Đang tải lịch hôm nay…")
        content.addWidget(self.detail)
        controls = QHBoxLayout()
        self.btn_check_in = button("Check-in", self.handle_check_in, True)
        self.btn_check_out = button("Check-out", self.handle_check_out)
        self.btn_check_in.setMinimumHeight(52)
        self.btn_check_out.setMinimumHeight(52)
        self.btn_check_in.setEnabled(False)
        self.btn_check_out.setEnabled(False)
        controls.addWidget(self.btn_check_in)
        controls.addWidget(self.btn_check_out)
        content.addLayout(controls)
        content.addWidget(
            label("Giờ chấm công được xác nhận bởi máy chủ. Chỉ check-out khi đã kết thúc giờ làm việc.")
        )
        self.root.addWidget(card)
        proof_widget = QWidget()
        proof_widget.setMaximumWidth(1100)
        proof = QHBoxLayout(proof_widget)
        proof.setContentsMargins(0, 0, 0, 0)
        proof.addWidget(label("Quên chấm công? Gửi ảnh và nội dung giải trình cho quản lý."), 1)
        self.btn_upload_proof = button("Gửi giải trình", self.handle_upload_proof)
        proof.addWidget(self.btn_upload_proof)
        self.root.addWidget(proof_widget)
        self.status.setMaximumWidth(1100)
        self.root.addWidget(self.status)
        self.root.addStretch()
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

    def on_show(self):
        self.load_schedule()

    def update_clock(self):
        if not self.isVisible():
            return
        now = local_now()
        self.clock_label.setText(now.strftime("%H:%M"))
        self.date_label.setText(now.strftime("%d/%m/%Y") + " · Giờ Việt Nam")

    def load_schedule(self, checked=False, *, message=""):
        if self.busy:
            return
        self.loading = True
        self._attendance_message = message
        self.shift_combo.setEnabled(False)
        self.status.setText("Đang đồng bộ ca làm việc…")
        self.btn_check_in.setEnabled(False)
        self.btn_check_out.setEnabled(False)
        user_id = self.current_profile["id"]
        self.tasks.submit(
            "schedule", lambda: self.supabase.get_today_schedule(user_id), self._apply_schedule_ui, self._schedule_failed
        )

    def _schedule_failed(self, message):
        self.loading = False
        self.schedules = []
        self.shift_combo.clear()
        self.shift_combo.setEnabled(True)
        self.apply_selection()
        self.detail.setText("Không thể xác định ca làm việc. Bấm Làm mới để thử lại.")
        self.error(message)

    def selected_schedule(self):
        index = self.shift_combo.currentIndex()
        return self.schedules[index] if 0 <= index < len(self.schedules) else None

    def _apply_schedule_ui(self, result):
        self.loading = False
        self.shift_combo.setEnabled(True)
        if not result.get("success"):
            self._schedule_failed(result.get("message", "Không thể tải ca làm việc."))
            return
        previous = (self.selected_schedule() or {}).get("id")
        self.schedules = sorted(
            result.get("schedules") or [],
            key=lambda s: ((s.get("shifts") or {}).get("start_time", ""), s.get("id", "")),
        )
        self.shift_combo.blockSignals(True)
        self.shift_combo.clear()
        for schedule in self.schedules:
            shift = schedule.get("shifts") or {}
            self.shift_combo.addItem(
                f"{shift.get('name', 'Ca làm')} · {str(shift.get('start_time', ''))[:5]} – {str(shift.get('end_time', ''))[:5]}",
                schedule.get("id"),
            )
        if previous:
            index = self.shift_combo.findData(previous)
            if index >= 0:
                self.shift_combo.setCurrentIndex(index)
        self.shift_combo.blockSignals(False)
        self.status.setText(self._attendance_message)
        self.apply_selection()

    def apply_selection(self, *_):
        schedule = self.selected_schedule()
        attendance = first_attendance(schedule or {})
        self.detail.setToolTip(
            f"Check-in: {timestamp_tooltip(attendance.get('check_in'))}\n"
            f"Check-out: {timestamp_tooltip(attendance.get('check_out'))}" if attendance else ""
        )
        available = not self.loading and bool(schedule) and schedule.get("status") == "scheduled"
        self.btn_check_in.setEnabled(available and not attendance and not self.busy)
        self.btn_check_out.setEnabled(
            available and bool(attendance) and not attendance.get("check_out") and not self.busy
        )
        if not schedule:
            self.detail.setText("Hôm nay chưa có ca làm việc được phân công.")
        elif schedule.get("status") == "leave":
            self.detail.setText("Ca này đã được duyệt nghỉ.")
        elif attendance.get("check_out"):
            self.detail.setText(
                f"Check-in {display_time(attendance.get('check_in'))} · Check-out {display_time(attendance.get('check_out'))}"
            )
        elif attendance:
            self.detail.setText(f"Đang trong ca · Check-in {display_time(attendance.get('check_in'))} · Chưa check-out")
        else:
            self.detail.setText("Chưa check-in. Chọn đúng ca làm việc trước khi chấm công.")
        notes = attendance_notes(attendance)
        if attendance and notes:
            self.detail.setText(f"{self.detail.text()} · {notes}")

    def handle_check_in(self):
        self._attendance_action(False)

    def handle_check_out(self):
        self._attendance_action(True)

    def _attendance_action(self, checkout):
        schedule = self.selected_schedule()
        if self.busy or self.loading or not schedule or schedule.get("status") != "scheduled":
            return
        attendance = first_attendance(schedule)
        if checkout and (not attendance or attendance.get("check_out")):
            return
        if not checkout and attendance:
            return
        self.busy = True
        self.apply_selection()
        self.shift_combo.setEnabled(False)
        self.status.setText("Đang ghi nhận giờ chấm công…")
        record_id = attendance.get("id") if checkout else schedule["id"]

        def work():
            identity = get_hardware_uuid()
            return (self.supabase.check_out if checkout else self.supabase.check_in)(record_id, identity)

        def done(result):
            self.busy = False
            self.shift_combo.setEnabled(True)
            if not result or not result.get("success"):
                self.apply_selection()
                self.error((result or {}).get("message", "Không thể ghi nhận chấm công."))
                return
            self.load_schedule(message="Check-out thành công." if checkout else "Check-in thành công.")

        def failed(message):
            self.busy = False
            self.shift_combo.setEnabled(True)
            self.apply_selection()
            self.error(message)

        self.tasks.submit("attendance", work, done, failed, replace=False)

    def handle_upload_proof(self):
        if not self.btn_upload_proof.isEnabled():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh minh chứng", "", "Ảnh (*.jpg *.jpeg *.png *.webp)"
        )
        if not path:
            return
        note, accepted = QInputDialog.getMultiLineText(self, "Gửi giải trình", "Nội dung giải trình:")
        if not accepted or not note.strip():
            return
        profile = self.current_profile
        if not profile.get("branch_id"):
            self.error("Tài khoản chưa có chi nhánh để gửi giải trình.")
            return
        self.btn_upload_proof.setEnabled(False)

        def done(result):
            self.btn_upload_proof.setEnabled(True)
            self.status.setText(
                "Đã gửi giải trình cho quản lý."
                if result.get("success")
                else result.get("message", "Không thể tải ảnh.")
            )

        def failed(message):
            self.btn_upload_proof.setEnabled(True)
            self.error(message)

        self.tasks.submit(
            "proof",
            lambda: self.supabase.upload_compressed_proof(
                path, profile["id"], profile["branch_id"], note.strip()
            ),
            done,
            failed,
            replace=False,
        )

    def open_attendance_history_dialog(self):
        from views_qt.attendance_history_dialog import AttendanceHistoryDialog

        dialog = AttendanceHistoryDialog(
            self, self.current_profile, target_user_id=self.current_profile["id"]
        )
        dialog.open()
