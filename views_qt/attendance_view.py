from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal, QTimer, Qt
from core.hardware import get_hardware_uuid
from core.supabase_service import SupabaseService
from core.qt_worker import QtWorker
from views_qt.attendance_history_dialog import AttendanceHistoryDialog

class AttendanceView(QWidget):
    logout_requested = Signal()

    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent)
        self.current_profile = current_profile or {}
        self.supabase = SupabaseService()
        self.device_uuid = get_hardware_uuid()

        self.today_schedule = None
        self.today_attendance = None
        self.worker = None

        self.setup_ui()
        self.load_schedule()

        # Timer đồng hồ thời gian thực mỗi 1 giây
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(15)

        # ================= 1. HEADER =================
        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 12px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 10, 20, 10)

        user_name = self.current_profile.get("full_name", "Dược sĩ")
        role = self.current_profile.get("role", "staff").upper()
        branch_info = self.current_profile.get("branches")
        branch_name = branch_info.get("name") if branch_info else "Tổng bộ / Quản trị"

        lbl_user = QLabel(f"👤 {user_name}  •  {role}")
        lbl_user.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; border: none;")
        h_layout.addWidget(lbl_user)

        lbl_branch = QLabel(f"🏥 {branch_name}")
        lbl_branch.setStyleSheet("font-size: 13px; color: #64B5F6; border: none; margin-left: 10px;")
        h_layout.addWidget(lbl_branch)

        h_layout.addStretch()

        btn_history = QPushButton("📜 LỊCH SỬ CHẤM CÔNG")
        btn_history.setFixedHeight(38)
        btn_history.setStyleSheet("""
            QPushButton {
                background-color: #17A2B8; color: white; font-weight: bold;
                border-radius: 8px; padding: 0px 16px; font-size: 13px; border: none;
            }
            QPushButton:hover { background-color: #138496; }
        """)
        btn_history.clicked.connect(self.open_attendance_history_dialog)
        h_layout.addWidget(btn_history)

        btn_logout = QPushButton("🚪 ĐĂNG XUẤT (GIAO CA)")
        btn_logout.setFixedHeight(38)
        btn_logout.setStyleSheet("""
            QPushButton {
                background-color: #D9534F; color: white; font-weight: bold;
                border-radius: 8px; padding: 0px 16px; font-size: 13px; border: none;
            }
            QPushButton:hover { background-color: #C9302C; }
        """)
        btn_logout.clicked.connect(self.handle_logout)
        h_layout.addWidget(btn_logout)

        root_layout.addWidget(header)

        # ================= 2. CONTENT AREA (CHIA 2 CỘT) =================
        content_box = QWidget()
        c_layout = QHBoxLayout(content_box)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(15)

        # Cột trái (Tỷ lệ 3): Đồng hồ & Nút Chấm Công
        left_col = QFrame()
        left_col.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 16px;")
        l_layout = QVBoxLayout(left_col)
        l_layout.setContentsMargins(30, 30, 30, 30)
        l_layout.setSpacing(15)

        # Đồng hồ số
        self.clock_label = QLabel("00:00:00")
        self.clock_label.setAlignment(Qt.AlignCenter)
        self.clock_label.setStyleSheet("font-family: Consolas, monospace; font-size: 54px; font-weight: bold; color: #2CC985; border: none;")
        l_layout.addWidget(self.clock_label)

        self.date_label = QLabel("")
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet("font-size: 14px; color: gray; border: none;")
        l_layout.addWidget(self.date_label)

        # Status box
        status_box = QFrame()
        status_box.setStyleSheet("background-color: #1A1A1A; border: 1px solid #2E2E2E; border-radius: 10px; padding: 12px;")
        st_layout = QVBoxLayout(status_box)
        self.status_text = QLabel("Đang kiểm tra lịch làm việc hôm nay...")
        self.status_text.setAlignment(Qt.AlignCenter)
        self.status_text.setWordWrap(True)
        self.status_text.setStyleSheet("font-size: 14px; font-weight: bold; color: #E0E0E0; border: none;")
        st_layout.addWidget(self.status_text)
        l_layout.addWidget(status_box)

        # 2 Nút Chấm Công Lớn
        btn_grid = QWidget()
        bg_layout = QHBoxLayout(btn_grid)
        bg_layout.setContentsMargins(0, 10, 0, 10)
        bg_layout.setSpacing(16)

        self.btn_check_in = QPushButton("✅ CHECK-IN\n(VÀO CA)")
        self.btn_check_in.setFixedHeight(68)
        self.btn_check_in.setStyleSheet("""
            QPushButton {
                background-color: #28A745; color: white; font-size: 15px; font-weight: bold;
                border-radius: 12px; border: none;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #384F3D; color: #7A9980; }
        """)
        self.btn_check_in.clicked.connect(self.handle_check_in)
        bg_layout.addWidget(self.btn_check_in)

        self.btn_check_out = QPushButton("🏁 CHECK-OUT\n(TAN CA)")
        self.btn_check_out.setFixedHeight(68)
        self.btn_check_out.setStyleSheet("""
            QPushButton {
                background-color: #FD7E14; color: white; font-size: 15px; font-weight: bold;
                border-radius: 12px; border: none;
            }
            QPushButton:hover { background-color: #E06A05; }
            QPushButton:disabled { background-color: #5A4330; color: #8E7A69; }
        """)
        self.btn_check_out.clicked.connect(self.handle_check_out)
        bg_layout.addWidget(self.btn_check_out)

        l_layout.addWidget(btn_grid)
        l_layout.addStretch()
        c_layout.addWidget(left_col, stretch=3)

        # Cột phải (Tỷ lệ 2): Thông tin ca & Minh chứng
        right_col = QFrame()
        right_col.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 16px;")
        r_layout = QVBoxLayout(right_col)
        r_layout.setContentsMargins(25, 25, 25, 25)
        r_layout.setSpacing(15)

        lbl_info_title = QLabel("THÔNG TIN CA HÔM NAY")
        lbl_info_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF; border: none;")
        r_layout.addWidget(lbl_info_title)

        self.shift_detail_label = QLabel("Chưa có dữ liệu ca làm")
        self.shift_detail_label.setStyleSheet("font-size: 13px; color: #CCCCCC; line-height: 1.5; border: none;")
        self.shift_detail_label.setWordWrap(True)
        r_layout.addWidget(self.shift_detail_label)

        # Box Giải trình quên chấm công (kèm ảnh)
        proof_box = QFrame()
        proof_box.setStyleSheet("background-color: #1A1A1A; border: 1px solid #2E2E2E; border-radius: 12px; padding: 15px;")
        pb_layout = QVBoxLayout(proof_box)
        pb_layout.setSpacing(8)

        lbl_pb_t = QLabel("Quên Check-out? Gửi giải trình")
        lbl_pb_t.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF; border: none;")
        pb_layout.addWidget(lbl_pb_t)

        lbl_pb_d = QLabel("Tải ảnh bằng chứng tại quầy để Quản lý duyệt lại công cho bạn.")
        lbl_pb_d.setStyleSheet("font-size: 11px; color: gray; border: none;")
        lbl_pb_d.setWordWrap(True)
        pb_layout.addWidget(lbl_pb_d)

        self.btn_upload_proof = QPushButton("📷 Tải ảnh bằng chứng")
        self.btn_upload_proof.setFixedHeight(36)
        self.btn_upload_proof.setStyleSheet("""
            QPushButton {
                background-color: #1F6AA5; color: white; font-weight: bold;
                border-radius: 8px; border: none; font-size: 12px;
            }
            QPushButton:hover { background-color: #257EC4; }
        """)
        self.btn_upload_proof.clicked.connect(self.handle_upload_proof)
        pb_layout.addWidget(self.btn_upload_proof)

        r_layout.addWidget(proof_box)
        r_layout.addStretch()
        c_layout.addWidget(right_col, stretch=2)

        root_layout.addWidget(content_box)

    def update_clock(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M:%S"))
        days = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        day_vn = days[now.weekday()]
        self.date_label.setText(f"{day_vn}, ngày {now.strftime('%d/%m/%Y')}")

        # Tự động mở nút Check-out khi đồng hồ điểm đúng hoặc qua giờ tan ca
        if self.today_schedule and self.today_attendance and not self.today_attendance.get("check_out"):
            shift = self.today_schedule.get("shifts") or {}
            end_time = shift.get("end_time", "16:00:00")
            try:
                end_h, end_m = map(int, end_time[:5].split(":"))
                shift_end_t = datetime.strptime(f"{end_h}:{end_m}", "%H:%M").time()
                if now.time() >= shift_end_t:
                    if not self.btn_check_out.isEnabled():
                        self.btn_check_out.setEnabled(True)
                        self.btn_check_out.setText("🏁 CHECK-OUT\n(TAN CA)")
                        self.status_text.setText(f"🔔 Đã hết ca ({end_time[:5]})! Vui lòng bấm Check-out hoàn thành ca.")
                        self.status_text.setStyleSheet("color: #28A745; font-size: 14px; font-weight: bold; border: none;")
                else:
                    if self.btn_check_out.isEnabled():
                        self.btn_check_out.setEnabled(False)
                        self.btn_check_out.setText(f"🏁 CHECK-OUT\n(HẾT CA LÚC {end_time[:5]})")
            except Exception:
                pass

    def load_schedule(self):
        user_id = self.current_profile.get("id")

        def fetch():
            return self.supabase.get_today_schedule(user_id)

        def on_schedule_loaded(res):
            self._apply_schedule_ui(res)

        self.worker = QtWorker(fetch)
        self.worker.result_ready.connect(on_schedule_loaded)
        self.worker.start()

    def _apply_schedule_ui(self, res):
        if not res.get("success") or not res.get("schedules"):
            self.status_text.setText("Hôm nay bạn không có lịch phân ca làm việc tại quầy!")
            self.status_text.setStyleSheet("color: gray; font-size: 14px; font-weight: bold; border: none;")
            self.shift_detail_label.setText("• Không có ca được xếp hôm nay.")
            self.btn_check_in.setEnabled(False)
            self.btn_check_out.setEnabled(False)
            return

        self.today_schedule = res["schedules"][0]
        shift = self.today_schedule.get("shifts", {})
        shift_name = shift.get("name", "Ca chưa đặt tên")
        start_time = shift.get("start_time", "08:00:00")
        end_time = shift.get("end_time", "16:00:00")

        raw_att = self.today_schedule.get("attendance")
        if isinstance(raw_att, list):
            self.today_attendance = raw_att[0] if raw_att else None
        elif isinstance(raw_att, dict):
            self.today_attendance = raw_att
        else:
            self.today_attendance = None

        detail_text = (
            f"• Ca: {shift_name}\n\n"
            f"• Thời gian: {start_time[:5]} - {end_time[:5]}\n\n"
            f"• Trạng thái lịch: {self.today_schedule.get('status', 'scheduled').upper()}"
        )
        self.shift_detail_label.setText(detail_text)

        if not self.today_attendance:
            # Chưa Check-in -> Mở nút Check-in, Khóa nút Check-out
            self.btn_check_in.setEnabled(True)
            self.btn_check_in.setText("✅ CHECK-IN\n(VÀO CA)")
            self.btn_check_out.setEnabled(False)
            self.btn_check_out.setText("🏁 CHECK-OUT\n(CHƯA VÀO CA)")
            self.status_text.setText("Bạn chưa Check-in vào ca. Vui lòng bấm Check-in!")
            self.status_text.setStyleSheet("color: #64B5F6; font-size: 14px; font-weight: bold; border: none;")
        else:
            # ĐÃ CHECK-IN -> KHÓA NÚT CHECK-IN NGAY LẬP TỨC
            self.btn_check_in.setEnabled(False)
            self.btn_check_in.setText("✅ ĐÃ CHECK-IN\n(ĐANG TRONG CA)")
            check_in_time = self.today_attendance.get("check_in", "")
            is_late = self.today_attendance.get("is_late", False)
            late_min = self.today_attendance.get("late_minutes", 0)
            time_display = check_in_time[11:19] if len(check_in_time) >= 19 else check_in_time

            if not self.today_attendance.get("check_out"):
                now_t = datetime.now().time()
                is_shift_ended = False
                try:
                    end_h, end_m = map(int, end_time[:5].split(":"))
                    shift_end_t = datetime.strptime(f"{end_h}:{end_m}", "%H:%M").time()
                    is_shift_ended = (now_t >= shift_end_t)
                except Exception:
                    is_shift_ended = True

                if is_shift_ended:
                    self.btn_check_out.setEnabled(True)
                    self.btn_check_out.setText("🏁 CHECK-OUT\n(TAN CA)")
                    if is_late:
                        self.status_text.setText(f"⚠️ Vào ca: {time_display} (Trễ {late_min}p). Đã hết ca ({end_time[:5]}), hãy bấm Check-out!")
                        self.status_text.setStyleSheet("color: #FD7E14; font-size: 14px; font-weight: bold; border: none;")
                    else:
                        self.status_text.setText(f"🔔 Đã hết ca làm việc ({end_time[:5]})! Vui lòng bấm Check-out hoàn thành ca.")
                        self.status_text.setStyleSheet("color: #28A745; font-size: 14px; font-weight: bold; border: none;")
                else:
                    self.btn_check_out.setEnabled(False)
                    self.btn_check_out.setText(f"🏁 CHECK-OUT\n(HẾT CA LÚC {end_time[:5]})")
                    if is_late:
                        self.status_text.setText(f"⚠️ Đã Check-in: {time_display} (ĐI TRỄ {late_min} PHÚT)\n(Đang trong ca làm việc. Ca kết thúc lúc {end_time[:5]})")
                        self.status_text.setStyleSheet("color: #FD7E14; font-size: 14px; font-weight: bold; border: none;")
                    else:
                        self.status_text.setText(f"✅ Đã Check-in đúng giờ: {time_display}\n(Đang trong ca làm việc. Ca kết thúc lúc {end_time[:5]})")
                        self.status_text.setStyleSheet("color: #28A745; font-size: 14px; font-weight: bold; border: none;")
            else:
                self.btn_check_in.setEnabled(False)
                self.btn_check_in.setText("✅ ĐÃ HOÀN THÀNH")
                self.btn_check_out.setEnabled(False)
                self.btn_check_out.setText("🏁 ĐÃ CHECK-OUT")
                check_out_time = self.today_attendance.get("check_out", "")
                out_display = check_out_time[11:19] if len(check_out_time) >= 19 else check_out_time
                self.status_text.setText(f"🎉 Bạn đã hoàn thành ca làm việc hôm nay!\n(Vào ca: {time_display}  •  Tan ca: {out_display})")
                self.status_text.setStyleSheet("color: #28A745; font-size: 14px; font-weight: bold; border: none;")

    def handle_check_in(self):
        if not self.today_schedule:
            QMessageBox.warning(self, "Cảnh báo", "Bạn không có ca làm việc hôm nay để Check-in!")
            return

        self.btn_check_in.setEnabled(False)
        self.btn_check_in.setText("ĐANG XỬ LÝ...")
        schedule_id = self.today_schedule.get("id")

        def worker():
            return self.supabase.check_in(schedule_id, self.device_uuid)

        def on_done(res):
            if isinstance(res, dict) and res.get("success"):
                self.btn_check_in.setEnabled(False)
                self.btn_check_in.setText("✅ ĐÃ CHECK-IN\n(ĐANG TRONG CA)")
                QMessageBox.information(self, "Thông báo Chấm công", res.get("message", "Check-in thành công!"))
            else:
                self.btn_check_in.setEnabled(True)
                self.btn_check_in.setText("✅ CHECK-IN\n(VÀO CA)")
                err = res.get("message") if isinstance(res, dict) else "Không thể ghi nhận giờ vào ca."
                QMessageBox.critical(self, "Thông báo", err)

            self.load_schedule()

        self.worker = QtWorker(worker)
        self.worker.result_ready.connect(on_done)
        self.worker.start()

    def handle_check_out(self):
        if not self.today_schedule or not self.today_attendance:
            QMessageBox.warning(self, "Cảnh báo", "Bạn chưa Check-in nên không thể Check-out!")
            return

        shift = self.today_schedule.get("shifts") or {}
        end_time = shift.get("end_time", "16:00:00")
        try:
            end_h, end_m = map(int, end_time[:5].split(":"))
            shift_end_t = datetime.strptime(f"{end_h}:{end_m}", "%H:%M").time()
            if datetime.now().time() < shift_end_t:
                QMessageBox.warning(
                    self, "Chưa đến giờ tan ca",
                    f"Ca làm việc của bạn kết thúc lúc {end_time[:5]}.\nHiện tại chưa hết ca nên bạn chưa được phép Check-out!"
                )
                return
        except Exception:
            pass

        self.btn_check_out.setEnabled(False)
        self.btn_check_out.setText("ĐANG XỬ LÝ...")
        attendance_id = self.today_attendance.get("id")

        def worker():
            return self.supabase.check_out(attendance_id, self.device_uuid)

        def on_done(res):
            if isinstance(res, dict) and res.get("success"):
                self.btn_check_out.setEnabled(False)
                self.btn_check_out.setText("🏁 ĐÃ CHECK-OUT")
                QMessageBox.information(self, "Thông báo Chấm công", res.get("message", "Check-out hoàn thành!"))
            else:
                self.btn_check_out.setEnabled(True)
                self.btn_check_out.setText("🏁 CHECK-OUT\n(TAN CA)")
                err = res.get("message") if isinstance(res, dict) else "Không thể ghi nhận giờ tan ca."
                QMessageBox.critical(self, "Thông báo", err)

            self.load_schedule()

        self.worker = QtWorker(worker)
        self.worker.result_ready.connect(on_done)
        self.worker.start()

    def handle_upload_proof(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh minh chứng", "", "Image files (*.jpg *.jpeg *.png *.webp)"
        )
        if not file_path:
            return

        user_id = self.current_profile.get("id")
        self.btn_upload_proof.setEnabled(False)
        self.btn_upload_proof.setText("Đang nén & tải ảnh...")

        def worker():
            return self.supabase.upload_compressed_proof(file_path, user_id)

        def on_done(res):
            self.btn_upload_proof.setEnabled(True)
            self.btn_upload_proof.setText("📷 Tải ảnh bằng chứng")
            if res.get("success"):
                QMessageBox.information(self, "Thành công", "Đã nén và gửi ảnh minh chứng lên hệ thống để Quản lý duyệt!")
            else:
                QMessageBox.critical(self, "Thông báo", res.get("message", "Không thể gửi ảnh minh chứng."))

        self.worker = QtWorker(worker)
        self.worker.result_ready.connect(on_done)
        self.worker.start()

    def handle_logout(self):
        self.clock_timer.stop()
        self.supabase.logout()
        self.logout_requested.emit()

    def open_attendance_history_dialog(self):
        dlg = AttendanceHistoryDialog(
            self,
            current_profile=self.current_profile,
            target_user_id=self.current_profile.get("id")
        )
        dlg.exec()
