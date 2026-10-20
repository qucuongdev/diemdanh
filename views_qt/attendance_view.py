from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QFrame, QComboBox, QFileDialog, QInputDialog
from core.domain import local_now, first_attendance, display_time
from core.hardware import get_hardware_uuid
from views_qt.common import Page, label, button


class AttendanceView(Page):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent, current_profile)
        self.schedules = []
        self.busy = False
        self.device_uuid = None
        self.heading(
            "Điểm danh",
            f"Xin chào {self.current_profile.get('full_name', '')}. Chúc bạn một ca làm việc thuận lợi.",
        )
        actions = QHBoxLayout()
        actions.addWidget(button("Lịch sử chấm công", self.open_attendance_history_dialog))
        actions.addWidget(button("Làm mới", self.load_schedule))
        actions.addStretch()
        self.root.addLayout(actions)
        card = QFrame()
        card.setObjectName("Card")
        content = QVBoxLayout(card)
        content.setContentsMargins(28, 28, 28, 28)
        content.setSpacing(20)
        self.clock_label = label(local_now().strftime("%H:%M:%S"))
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
        self.btn_check_in = button("Vào ca", self.handle_check_in, True)
        self.btn_check_out = button("Tan ca", self.handle_check_out)
        self.btn_check_in.setMinimumHeight(52)
        self.btn_check_out.setMinimumHeight(52)
        self.btn_check_in.setEnabled(False)
        self.btn_check_out.setEnabled(False)
        controls.addWidget(self.btn_check_in)
        controls.addWidget(self.btn_check_out)
        content.addLayout(controls)
        content.addWidget(
            label("Giờ chấm công được xác nhận bởi máy chủ. Chỉ bấm tan ca khi đã kết thúc giờ làm việc.")
        )
        self.root.addWidget(card)
        proof = QHBoxLayout()
        proof.addWidget(label("Quên chấm công? Gửi ảnh và nội dung giải trình cho quản lý."), 1)
        self.btn_upload_proof = button("Gửi giải trình", self.handle_upload_proof)
        proof.addWidget(self.btn_upload_proof)
        self.root.addLayout(proof)
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
        self.clock_label.setText(now.strftime("%H:%M:%S"))
        self.date_label.setText(now.strftime("%d/%m/%Y") + " · Giờ Việt Nam")

    def load_schedule(self):
        if self.busy:
            return
        self.status.setText("Đang đồng bộ ca làm việc…")
        self.btn_check_in.setEnabled(False)
        self.btn_check_out.setEnabled(False)
        user_id = self.current_profile["id"]
        self.tasks.submit(
            "schedule", lambda: self.supabase.get_today_schedule(user_id), self._apply_schedule_ui, self.error
        )

    def selected_schedule(self):
        index = self.shift_combo.currentIndex()
        return self.schedules[index] if 0 <= index < len(self.schedules) else None

    def _apply_schedule_ui(self, result):
        if not result.get("success"):
            self.schedules = []
            self.shift_combo.clear()
            self.apply_selection()
            self.error(result.get("message", "Không thể tải ca làm việc."))
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
        self.status.clear()
        self.apply_selection()

    def apply_selection(self, *_):
        schedule = self.selected_schedule()
        attendance = first_attendance(schedule or {})
        available = bool(schedule) and schedule.get("status") not in ("leave", "absent", "completed")
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
                f"Đã hoàn thành · Vào {display_time(attendance.get('check_in'))} · Tan ca {display_time(attendance.get('check_out'))}"
            )
        elif attendance:
            self.detail.setText(f"Đang trong ca · Đã vào lúc {display_time(attendance.get('check_in'))}")
        else:
            self.detail.setText("Chưa vào ca. Chọn đúng ca làm việc trước khi chấm công.")

    def handle_check_in(self):
        self._attendance_action(False)

    def handle_check_out(self):
        self._attendance_action(True)

    def _attendance_action(self, checkout):
        schedule = self.selected_schedule()
        if self.busy or not schedule:
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
            self.status.setText(
                result.get("message", "Đã ghi nhận.") if result else "Không thể ghi nhận chấm công."
            )
            self.load_schedule()

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
