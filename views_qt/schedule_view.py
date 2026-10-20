import calendar
from datetime import datetime, date, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QScrollArea, QFrame, QDialog, QLineEdit, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from core.supabase_service import SupabaseService
from core.qt_worker import QtWorker
from views_qt.attendance_history_dialog import AttendanceHistoryDialog

def clean_staff_name(name_str: str) -> str:
    if not name_str:
        return "Nhân viên"
    c_name = name_str.strip()
    for sfx in [" (Admin)", " (admin)", " (Quản lý)", " (Store Manager)", " (Staff)", " (Dược sĩ)"]:
        if c_name.endswith(sfx):
            c_name = c_name[:-len(sfx)].strip()
            break
    if len(c_name) > 15:
        return c_name[:14] + "…"
    return c_name

class DayCellWidget(QFrame):
    clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumHeight(135)
        self.setStyleSheet("""
            DayCellWidget {
                background-color: #242424;
                border: 1px solid #333333;
                border-radius: 8px;
            }
            DayCellWidget:hover {
                border: 1px solid #4FA3F7;
            }
        """)

        self.cell_data = {
            "date_key": None,
            "is_current_month": False
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        # Top bar
        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(26)
        self.top_bar.setStyleSheet("background-color: #2A2A2A; border-radius: 4px; padding: 0 4px;")
        tb_layout = QHBoxLayout(self.top_bar)
        tb_layout.setContentsMargins(4, 2, 4, 2)

        self.lbl_date = QLabel("")
        self.lbl_date.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888;")
        tb_layout.addWidget(self.lbl_date)
        tb_layout.addStretch()

        self.lbl_time = QLabel("")
        self.lbl_time.setStyleSheet("font-size: 9px; font-weight: bold; color: #888888;")
        tb_layout.addWidget(self.lbl_time)
        layout.addWidget(self.top_bar)

        # Content container
        self.content_box = QWidget()
        c_layout = QVBoxLayout(self.content_box)
        c_layout.setContentsMargins(2, 2, 2, 2)
        c_layout.setSpacing(2)

        # Empty state label
        self.lbl_empty = QLabel("⚪ Nghỉ / Không ca")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setStyleSheet("color: #666666; font-size: 10px; padding: 15px 0;")
        c_layout.addWidget(self.lbl_empty)

        # Slot 1
        self.slot1_box = QFrame()
        self.slot1_box.setStyleSheet("background-color: #2D3035; border-radius: 4px; padding: 2px 4px;")
        s1_layout = QVBoxLayout(self.slot1_box)
        s1_layout.setContentsMargins(4, 2, 4, 2)
        s1_layout.setSpacing(1)
        self.lbl_s1_name = QLabel("")
        self.lbl_s1_name.setStyleSheet("font-size: 10px; font-weight: bold; color: #4FA3F7;")
        self.lbl_s1_shift = QLabel("")
        self.lbl_s1_shift.setStyleSheet("font-size: 9px;")
        s1_layout.addWidget(self.lbl_s1_name)
        s1_layout.addWidget(self.lbl_s1_shift)
        c_layout.addWidget(self.slot1_box)

        # Slot 2
        self.slot2_box = QFrame()
        self.slot2_box.setStyleSheet("background-color: #2D3035; border-radius: 4px; padding: 2px 4px;")
        s2_layout = QVBoxLayout(self.slot2_box)
        s2_layout.setContentsMargins(4, 2, 4, 2)
        s2_layout.setSpacing(1)
        self.lbl_s2_name = QLabel("")
        self.lbl_s2_name.setStyleSheet("font-size: 10px; font-weight: bold; color: #4FA3F7;")
        self.lbl_s2_shift = QLabel("")
        self.lbl_s2_shift.setStyleSheet("font-size: 9px;")
        s2_layout.addWidget(self.lbl_s2_name)
        s2_layout.addWidget(self.lbl_s2_shift)
        c_layout.addWidget(self.slot2_box)

        # More shifts label
        self.lbl_more = QLabel("")
        self.lbl_more.setStyleSheet("font-size: 8px; font-weight: bold; color: #4FA3F7; padding-left: 2px;")
        c_layout.addWidget(self.lbl_more)

        c_layout.addStretch()
        layout.addWidget(self.content_box)

        # Hide initially
        self.slot1_box.setVisible(False)
        self.slot2_box.setVisible(False)
        self.lbl_more.setVisible(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.cell_data)
        super().mousePressEvent(event)


class AddScheduleDialog(QDialog):
    def __init__(self, parent=None, supabase=None, default_staff_name=None):
        super().__init__(parent)
        self.supabase = supabase or SupabaseService()
        self.default_staff_name = default_staff_name
        self.setWindowTitle("Xếp Ca Làm Việc Mới")
        self.resize(460, 480)
        self.setStyleSheet("""
            QDialog { background-color: #1A1A1A; }
            QLabel { color: #E0E0E0; font-size: 12px; font-weight: bold; }
            QLineEdit, QComboBox {
                background-color: #2A2A2A;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 6px 10px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #1F6AA5; }
        """)
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)

        title = QLabel("XẾP CA LÀM VIỆC MỚI")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4FA3F7; margin-bottom: 8px;")
        layout.addWidget(title)

        # 1. Branch
        layout.addWidget(QLabel("1. Chọn Chi nhánh:"))
        self.branch_combo = QComboBox()
        layout.addWidget(self.branch_combo)

        # 2. Staff
        layout.addWidget(QLabel("2. Chọn Nhân viên:"))
        self.staff_combo = QComboBox()
        layout.addWidget(self.staff_combo)

        # 3. Shift
        layout.addWidget(QLabel("3. Chọn Ca làm việc:"))
        self.shift_combo = QComboBox()
        layout.addWidget(self.shift_combo)

        # 4. Work date
        layout.addWidget(QLabel("4. Ngày làm việc (YYYY-MM-DD):"))
        self.date_input = QLineEdit(date.today().isoformat())
        layout.addWidget(self.date_input)

        layout.addSpacing(10)

        # Save button
        self.btn_save = QPushButton("💾 LƯU CA LÀM VIỆC")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        self.btn_save.clicked.connect(self.save_schedule)
        layout.addWidget(self.btn_save)

    def load_data(self):
        self.branches = self.supabase.get_branches() or []
        self.branch_map = {b["name"]: b["id"] for b in self.branches}
        self.branch_combo.addItems(list(self.branch_map.keys()))

        self.staffs = self.supabase.get_staff_list() or []
        self.staff_options = [f"{s.get('full_name')} ({s.get('role', 'staff')})" for s in self.staffs]
        self.staff_map = {opt: s for opt, s in zip(self.staff_options, self.staffs)}
        self.staff_combo.addItems(self.staff_options)
        if self.default_staff_name:
            for idx, opt in enumerate(self.staff_options):
                if self.default_staff_name in opt:
                    self.staff_combo.setCurrentIndex(idx)
                    break

        self.shifts = self.supabase.get_shifts() or []
        self.shift_options = [f"{s.get('name')} ({s.get('start_time')[:5]}-{s.get('end_time')[:5]})" for s in self.shifts]
        self.shift_map = {opt: s for opt, s in zip(self.shift_options, self.shifts)}
        self.shift_combo.addItems(self.shift_options)

    def save_schedule(self):
        work_date = self.date_input.text().strip()
        try:
            datetime.strptime(work_date, "%Y-%m-%d")
        except ValueError:
            QMessageBox.critical(self, "Lỗi", "Ngày phải đúng định dạng YYYY-MM-DD!")
            return

        chosen_branch_name = self.branch_combo.currentText()
        chosen_branch_id = self.branch_map.get(chosen_branch_name)

        staff_sel = self.staff_combo.currentText()
        target_staff = self.staff_map.get(staff_sel)
        if not target_staff:
            QMessageBox.warning(self, "Lưu ý", "Vui lòng chọn nhân viên hợp lệ!")
            return

        shift_sel = self.shift_combo.currentText()
        target_shift = self.shift_map.get(shift_sel)
        if not target_shift:
            QMessageBox.warning(self, "Lưu ý", "Vui lòng chọn ca làm việc hợp lệ!")
            return

        branch = chosen_branch_id or target_shift.get("branch_id") or target_staff.get("branch_id") or (self.branches[0]["id"] if self.branches else None)

        self.btn_save.setEnabled(False)
        self.btn_save.setText("Đang lưu...")

        def do_save():
            return self.supabase.create_schedule(
                branch_id=branch,
                user_id=target_staff.get("id"),
                shift_id=target_shift.get("id"),
                work_date=work_date
            )

        def on_done(res):
            self.btn_save.setEnabled(True)
            self.btn_save.setText("💾 LƯU CA LÀM VIỆC")
            if res.get("success"):
                QMessageBox.information(self, "Thành công", f"Đã xếp ca thành công cho {target_staff.get('full_name')}!")
                self.accept()
            else:
                QMessageBox.critical(self, "Lỗi", res.get("message", "Không thể xếp ca làm việc. Vui lòng thử lại!"))

        def on_err(err):
            self.btn_save.setEnabled(True)
            self.btn_save.setText("💾 LƯU CA LÀM VIỆC")
            QMessageBox.critical(self, "Lỗi", f"Có lỗi xảy ra: {err}")

        self.worker = QtWorker(do_save)
        self.worker.result_ready.connect(on_done)
        self.worker.error_occurred.connect(on_err)
        self.worker.start()


class RequestLeaveDialog(QDialog):
    def __init__(self, parent=None, supabase=None, current_profile=None):
        super().__init__(parent)
        self.supabase = supabase or SupabaseService()
        self.current_profile = current_profile or {}
        self.setWindowTitle("Đề Xuất Xin Nghỉ Phép")
        self.resize(440, 390)
        self.setStyleSheet("""
            QDialog { background-color: #1A1A1A; }
            QLabel { color: #E0E0E0; font-size: 12px; font-weight: bold; }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #2A2A2A;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 6px 10px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border: 1px solid #1F6AA5; }
        """)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(10)

        title = QLabel("ĐỀ XUẤT XIN NGHỈ PHÉP")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #FD7E14; margin-bottom: 5px;")
        layout.addWidget(title)

        # Date input
        layout.addWidget(QLabel("Ngày muốn xin nghỉ (YYYY-MM-DD):"))
        self.date_input = QLineEdit(date.today().isoformat())
        layout.addWidget(self.date_input)

        # Leave type
        layout.addWidget(QLabel("Loại đề xuất:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Nghỉ ốm (sick)",
            "Phép năm (annual)",
            "Việc riêng không lương (unpaid)",
            "Xin đổi ca (swap)"
        ])
        layout.addWidget(self.type_combo)

        # Reason
        layout.addWidget(QLabel("Lý do chi tiết:"))
        self.reason_input = QTextEdit()
        self.reason_input.setFixedHeight(75)
        layout.addWidget(self.reason_input)

        layout.addSpacing(8)

        self.btn_submit = QPushButton("GỬI ĐỀ XUẤT NGHỈ")
        self.btn_submit.setFixedHeight(38)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #FD7E14;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #E06A05; }
        """)
        self.btn_submit.clicked.connect(self.submit_leave)
        layout.addWidget(self.btn_submit)

    def submit_leave(self):
        reason = self.reason_input.toPlainText().strip()
        w_date = self.date_input.text().strip()
        if not reason:
            QMessageBox.warning(self, "Lưu ý", "Vui lòng nhập lý do xin nghỉ!")
            return

        target_user_id = self.current_profile.get("id")
        self.btn_submit.setEnabled(False)
        self.btn_submit.setText("Đang gửi...")

        def do_submit():
            schedules = self.supabase.get_schedules_range(user_id=target_user_id, start_date=w_date, end_date=w_date)
            if not schedules:
                return {"success": False, "message": f"Bạn không có ca làm việc nào được xếp vào ngày {w_date} để xin nghỉ!"}
            sched = schedules[0]
            raw_type = self.type_combo.currentText().split("(")[-1].replace(")", "").strip()
            return self.supabase.submit_leave_request(sched.get("id"), sched.get("branch_id"), raw_type, reason)

        def on_done(res):
            self.btn_submit.setEnabled(True)
            self.btn_submit.setText("GỬI ĐỀ XUẤT NGHỈ")
            if res.get("success"):
                QMessageBox.information(self, "Thành công", "Đơn xin nghỉ đã được gửi tới Cửa hàng trưởng duyệt!")
                self.accept()
            else:
                QMessageBox.critical(self, "Thông báo", res.get("message", "Không thể gửi đơn xin nghỉ. Vui lòng thử lại sau!"))

        def on_err(err):
            self.btn_submit.setEnabled(True)
            self.btn_submit.setText("GỬI ĐỀ XUẤT NGHỈ")
            QMessageBox.critical(self, "Lỗi", f"Có lỗi xảy ra: {err}")

        self.worker = QtWorker(do_submit)
        self.worker.result_ready.connect(on_done)
        self.worker.error_occurred.connect(on_err)
        self.worker.start()


class ScheduleView(QWidget):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent)
        self.current_profile = current_profile or {}
        self.supabase = SupabaseService()

        today = date.today()
        self.current_year = today.year
        self.current_month = today.month

        self.user_role = self.current_profile.get("role", "staff")
        self.branch_id = self.current_profile.get("branch_id")

        self.branches = []
        self.branch_map = {}
        self.staffs = []
        self.staff_map = {}
        self._schedule_cache = {}
        self.day_cells = []
        self.fetch_worker = None

        self.setup_ui()
        self.load_filters()
        self.render_month_calendar()

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(15, 15, 15, 15)
        root_layout.setSpacing(8)

        # 1. Header Frame
        header = QFrame()
        header.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px; padding: 10px;")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(10)

        # Top row: Month navigation & Action buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # Nav buttons
        self.btn_prev_month = QPushButton("◀")
        self.btn_prev_month.setFixedSize(34, 30)
        self.btn_prev_month.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #444444; border-radius: 4px; color: white; font-weight: bold; } QPushButton:hover { background-color: #333333; }")
        self.btn_prev_month.clicked.connect(self.prev_month)
        top_row.addWidget(self.btn_prev_month)

        self.lbl_month_title = QLabel("")
        self.lbl_month_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #4FA3F7; padding: 0 4px;")
        top_row.addWidget(self.lbl_month_title)

        self.btn_next_month = QPushButton("▶")
        self.btn_next_month.setFixedSize(34, 30)
        self.btn_next_month.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #444444; border-radius: 4px; color: white; font-weight: bold; } QPushButton:hover { background-color: #333333; }")
        self.btn_next_month.clicked.connect(self.next_month)
        top_row.addWidget(self.btn_next_month)

        self.btn_today = QPushButton("Hôm nay")
        self.btn_today.setFixedHeight(30)
        self.btn_today.setStyleSheet("QPushButton { background-color: #1F6AA5; color: white; font-weight: bold; border: none; border-radius: 4px; padding: 0 12px; } QPushButton:hover { background-color: #155585; }")
        self.btn_today.clicked.connect(self.goto_today)
        top_row.addWidget(self.btn_today)

        self.lbl_date_range = QLabel("")
        self.lbl_date_range.setStyleSheet("font-size: 11px; color: #888888; padding-left: 10px;")
        top_row.addWidget(self.lbl_date_range)

        top_row.addStretch()

        # Action buttons
        if self.user_role in ("storemanager", "admin"):
            self.btn_add_shift = QPushButton("➕ Xếp ca làm việc")
            self.btn_add_shift.setFixedHeight(32)
            self.btn_add_shift.setStyleSheet("QPushButton { background-color: #28A745; color: white; font-weight: bold; border: none; border-radius: 6px; padding: 0 14px; } QPushButton:hover { background-color: #218838; }")
            self.btn_add_shift.clicked.connect(self.open_add_schedule_modal)
            top_row.addWidget(self.btn_add_shift)

        self.btn_history = QPushButton("📜 Lịch sử Check-in/out")
        self.btn_history.setFixedHeight(32)
        self.btn_history.setStyleSheet("QPushButton { background-color: #17A2B8; color: white; font-weight: bold; border: none; border-radius: 6px; padding: 0 14px; } QPushButton:hover { background-color: #138496; }")
        self.btn_history.clicked.connect(lambda: self.open_attendance_history_modal())
        top_row.addWidget(self.btn_history)

        self.btn_request_leave = QPushButton("📝 Đề xuất nghỉ")
        self.btn_request_leave.setFixedHeight(32)
        self.btn_request_leave.setStyleSheet("QPushButton { background-color: #FD7E14; color: white; font-weight: bold; border: none; border-radius: 6px; padding: 0 14px; } QPushButton:hover { background-color: #E06A05; }")
        self.btn_request_leave.clicked.connect(self.open_general_leave_modal)
        top_row.addWidget(self.btn_request_leave)

        h_layout.addLayout(top_row)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        lbl_filter = QLabel("Xem lịch của:")
        lbl_filter.setStyleSheet("font-size: 12px; font-weight: bold; color: #888888;")
        filter_row.addWidget(lbl_filter)

        self.staff_combo = QComboBox()
        self.staff_combo.setFixedWidth(220)
        self.staff_combo.setStyleSheet("QComboBox { background-color: #2A2A2A; border: 1px solid #444444; border-radius: 5px; color: white; padding: 4px 8px; }")
        self.staff_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_row.addWidget(self.staff_combo)

        self.branch_combo = QComboBox()
        self.branch_combo.setFixedWidth(180)
        self.branch_combo.setStyleSheet("QComboBox { background-color: #2A2A2A; border: 1px solid #444444; border-radius: 5px; color: white; padding: 4px 8px; }")
        self.branch_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_row.addWidget(self.branch_combo)

        self.btn_refresh = QPushButton("🔄 Tải lại")
        self.btn_refresh.setFixedSize(85, 30)
        self.btn_refresh.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #444444; border-radius: 5px; color: white; font-weight: bold; } QPushButton:hover { background-color: #333333; }")
        self.btn_refresh.clicked.connect(self.refresh_calendar)
        filter_row.addWidget(self.btn_refresh)

        filter_row.addStretch()
        h_layout.addLayout(filter_row)

        root_layout.addWidget(header)

        # 2. Legend bar
        legend_frame = QFrame()
        legend_frame.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 8px; padding: 6px 12px;")
        leg_layout = QHBoxLayout(legend_frame)
        leg_layout.setContentsMargins(10, 4, 10, 4)
        leg_layout.setSpacing(20)

        legends = [
            ("🟢 Đủ công / Đúng giờ", "#28A745"),
            ("🟠 Ca vào muộn / Về sớm", "#FD7E14"),
            ("❌ Ca nghỉ / Vắng", "#DC3545"),
            ("🔵 Ca sắp diễn ra", "#3B8ED0"),
            ("⚪ Ngày nghỉ", "#888888")
        ]
        for txt, color in legends:
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
            leg_layout.addWidget(lbl)
        leg_layout.addStretch()

        root_layout.addWidget(legend_frame)

        # 3. Calendar Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        grid_container = QWidget()
        grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setContentsMargins(0, 4, 0, 4)

        headers = ["THỨ HAI", "THỨ BA", "THỨ TƯ", "THỨ NĂM", "THỨ SÁU", "THỨ BẢY", "CHỦ NHẬT"]
        for col_idx, h in enumerate(headers):
            h_lbl = QLabel(h)
            h_lbl.setAlignment(Qt.AlignCenter)
            h_lbl.setFixedHeight(30)
            h_lbl.setStyleSheet("background-color: #242424; color: #AAAAAA; font-size: 11px; font-weight: bold; border-radius: 6px; border: 1px solid #333333;")
            self.grid_layout.addWidget(h_lbl, 0, col_idx)

        self.day_cells = []
        for cell_idx in range(42):
            row_idx = (cell_idx // 7) + 1
            col_idx = cell_idx % 7
            cell = DayCellWidget()
            cell.clicked.connect(self._on_cell_clicked)
            self.grid_layout.addWidget(cell, row_idx, col_idx)
            self.day_cells.append(cell)

        scroll.setWidget(grid_container)
        root_layout.addWidget(scroll)

    def _on_cell_clicked(self, cell_data):
        d_key = cell_data.get("date_key")
        if d_key and cell_data.get("is_current_month"):
            self.open_attendance_history_modal(target_date=d_key)

    def load_filters(self):
        if self.user_role == "staff":
            my_name = self.current_profile.get("full_name", "Nhân viên")
            self.staff_combo.addItem(my_name)
            self.staff_combo.setEnabled(False)
        else:
            self.staff_combo.addItem("Tất cả nhân viên")

        self.branch_combo.addItem("Tất cả chi nhánh")

        def fetch_meta():
            b = self.supabase.get_branches()
            s = self.supabase.get_staff_list()
            return b, s

        def on_meta_done(result):
            branches, staffs = result
            self.branches = branches or []
            self.branch_map = {b["name"]: b["id"] for b in self.branches}
            self.branch_combo.blockSignals(True)
            self.branch_combo.clear()
            self.branch_combo.addItem("Tất cả chi nhánh")
            self.branch_combo.addItems(list(self.branch_map.keys()))
            self.branch_combo.blockSignals(False)

            self.staffs = staffs or []
            self.staff_map = {s["full_name"]: s["id"] for s in self.staffs}
            staff_names = list(self.staff_map.keys())

            self.staff_combo.blockSignals(True)
            self.staff_combo.clear()
            if self.user_role == "staff":
                my_name = self.current_profile.get("full_name")
                self.staff_combo.addItem(my_name)
                self.staff_combo.setEnabled(False)
            else:
                self.staff_combo.addItem("Tất cả nhân viên")
                self.staff_combo.addItems(staff_names)
            self.staff_combo.blockSignals(False)

            self.render_month_calendar()

        self.meta_worker = QtWorker(fetch_meta)
        self.meta_worker.result_ready.connect(on_meta_done)
        self.meta_worker.start()

    def on_filter_changed(self):
        self.render_month_calendar()

    def prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.render_month_calendar()

    def next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.render_month_calendar()

    def goto_today(self):
        today = date.today()
        self.current_year = today.year
        self.current_month = today.month
        self.render_month_calendar()

    def refresh_calendar(self):
        self._schedule_cache.clear()
        self.render_month_calendar()

    def render_month_calendar(self):
        self.lbl_month_title.setText(f"T{self.current_month}/{self.current_year}")
        days_in_month = calendar.monthrange(self.current_year, self.current_month)[1]
        self.lbl_date_range.setText(
            f"Khoảng thời gian: 01/{self.current_month:02d} - {days_in_month:02d}/{self.current_month:02d}/{self.current_year}"
        )

        start_date_str = f"{self.current_year:04d}-{self.current_month:02d}-01"
        end_date_str = f"{self.current_year:04d}-{self.current_month:02d}-{days_in_month:02d}"

        target_user_id = self.staff_map.get(self.staff_combo.currentText())
        if not target_user_id and self.user_role == "staff":
            target_user_id = self.current_profile.get("id")

        b_name = self.branch_combo.currentText()
        target_branch_id = self.branch_map.get(b_name)

        cache_key = f"{target_branch_id}_{target_user_id}_{start_date_str}_{end_date_str}"

        if cache_key in self._schedule_cache:
            self._update_grid_data(self._schedule_cache[cache_key])
            return

        def fetch_schedules():
            return self.supabase.get_schedules_range(
                branch_id=target_branch_id,
                user_id=target_user_id,
                start_date=start_date_str,
                end_date=end_date_str
            )

        def on_schedules_done(schedules):
            self._schedule_cache[cache_key] = schedules
            self._update_grid_data(schedules)

        self.fetch_worker = QtWorker(fetch_schedules)
        self.fetch_worker.result_ready.connect(on_schedules_done)
        self.fetch_worker.start()

    def _update_grid_data(self, schedules):
        schedules_by_date = {}
        for s in schedules:
            w_date = s.get("work_date")
            if w_date not in schedules_by_date:
                schedules_by_date[w_date] = []
            schedules_by_date[w_date].append(s)

        first_day_of_month = date(self.current_year, self.current_month, 1)
        start_weekday = first_day_of_month.weekday()
        start_calendar_date = first_day_of_month - timedelta(days=start_weekday)
        today_val = date.today()

        for cell_idx, cell in enumerate(self.day_cells):
            cur_date = start_calendar_date + timedelta(days=cell_idx)
            is_current_month = (cur_date.month == self.current_month)
            is_today = (cur_date == today_val)
            date_key = cur_date.isoformat()

            cell.cell_data["date_key"] = date_key
            cell.cell_data["is_current_month"] = is_current_month

            if not is_current_month:
                cell.setStyleSheet("""
                    DayCellWidget {
                        background-color: #1A1A1A;
                        border: 1px solid #222222;
                        border-radius: 8px;
                    }
                """)
                cell.top_bar.setStyleSheet("background-color: transparent;")
                cell.lbl_date.setText(f"{cur_date.day:02d}/{cur_date.month:02d}")
                cell.lbl_date.setStyleSheet("font-size: 11px; font-weight: bold; color: #555555;")
                cell.lbl_time.setText("")
                cell.lbl_empty.setVisible(False)
                cell.slot1_box.setVisible(False)
                cell.slot2_box.setVisible(False)
                cell.lbl_more.setVisible(False)
                continue

            # In current month
            if is_today:
                cell.setStyleSheet("""
                    DayCellWidget {
                        background-color: #242424;
                        border: 2px solid #1F6AA5;
                        border-radius: 8px;
                    }
                """)
            else:
                cell.setStyleSheet("""
                    DayCellWidget {
                        background-color: #242424;
                        border: 1px solid #333333;
                        border-radius: 8px;
                    }
                    DayCellWidget:hover {
                        border: 1px solid #4FA3F7;
                    }
                """)

            day_schedules = schedules_by_date.get(date_key, [])
            total_shifts = len(day_schedules)
            has_late = False
            has_attended = False
            first_check_in = None
            last_check_out = None
            is_all_leave = (total_shifts > 0 and all(s.get("status") == "leave" for s in day_schedules))

            for s in day_schedules:
                att_list = s.get("attendance") or []
                if att_list:
                    att = att_list[0] if isinstance(att_list, list) else att_list
                    cin = att.get("check_in")
                    cout = att.get("check_out")
                    if cin:
                        has_attended = True
                        cin_t = cin[11:16]
                        if not first_check_in or cin_t < first_check_in:
                            first_check_in = cin_t
                    if cout:
                        cout_t = cout[11:16]
                        if not last_check_out or cout_t > last_check_out:
                            last_check_out = cout_t
                    if att.get("is_late"):
                        has_late = True

            # Header top_bar styling
            if total_shifts == 0:
                header_bg = "#2A2A2A"
                header_text_color = "#888888"
                time_range_txt = ""
            elif is_all_leave:
                header_bg = "#DC3545"
                header_text_color = "white"
                time_range_txt = "Nghỉ phép"
            elif has_attended:
                header_bg = "#FD7E14" if has_late else "#28A745"
                header_text_color = "white"
                time_range_txt = f"🕒 {first_check_in or '--'}-{last_check_out or '--'}"
            else:
                header_bg = "#18324F"
                header_text_color = "#4FA3F7"
                time_range_txt = "Sắp tới"

            cell.top_bar.setStyleSheet(f"background-color: {header_bg}; border-radius: 4px; padding: 0 4px;")
            cell.lbl_date.setText(f"{cur_date.day:02d}/{cur_date.month:02d}")
            cell.lbl_date.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {header_text_color};")
            cell.lbl_time.setText(time_range_txt)
            cell.lbl_time.setStyleSheet(f"font-size: 9px; font-weight: bold; color: {header_text_color};")

            if total_shifts == 0:
                cell.lbl_empty.setVisible(True)
                cell.slot1_box.setVisible(False)
                cell.slot2_box.setVisible(False)
                cell.lbl_more.setVisible(False)
                continue

            cell.lbl_empty.setVisible(False)

            # Slot 1
            if total_shifts >= 1:
                s1 = day_schedules[0]
                sh1 = s1.get("shifts") or {}
                st1 = sh1.get("start_time", "")[:5]
                et1 = sh1.get("end_time", "")[:5]
                p1 = s1.get("profiles") or {}
                emp1 = clean_staff_name(p1.get("full_name"))

                raw_att1 = s1.get("attendance")
                att1 = (raw_att1[0] if isinstance(raw_att1, list) else raw_att1) or {}
                is_late1 = att1.get("is_late", False)

                if s1.get("status") == "leave":
                    icon1, color1, sub1 = "❌", "#DC3545", "Nghỉ"
                elif att1.get("check_in"):
                    icon1 = "⏰" if is_late1 else "✔"
                    color1 = "#FD7E14" if is_late1 else "#28A745"
                    sub1 = f"Đến {att1.get('check_in')[11:16]}"
                else:
                    icon1, color1, sub1 = "📅", "#AAAAAA", "Chưa vào"

                cell.lbl_s1_name.setText(f"👤 {emp1}")
                cell.lbl_s1_shift.setText(f"{icon1} {st1}-{et1} ({sub1})")
                cell.lbl_s1_shift.setStyleSheet(f"font-size: 9px; color: {color1};")
                cell.slot1_box.setVisible(True)
            else:
                cell.slot1_box.setVisible(False)

            # Slot 2
            if total_shifts >= 2:
                s2 = day_schedules[1]
                sh2 = s2.get("shifts") or {}
                st2 = sh2.get("start_time", "")[:5]
                et2 = sh2.get("end_time", "")[:5]
                p2 = s2.get("profiles") or {}
                emp2 = clean_staff_name(p2.get("full_name"))

                raw_att2 = s2.get("attendance")
                att2 = (raw_att2[0] if isinstance(raw_att2, list) else raw_att2) or {}
                is_late2 = att2.get("is_late", False)

                if s2.get("status") == "leave":
                    icon2, color2, sub2 = "❌", "#DC3545", "Nghỉ"
                elif att2.get("check_in"):
                    icon2 = "⏰" if is_late2 else "✔"
                    color2 = "#FD7E14" if is_late2 else "#28A745"
                    sub2 = f"Đến {att2.get('check_in')[11:16]}"
                else:
                    icon2, color2, sub2 = "📅", "#AAAAAA", "Chưa vào"

                cell.lbl_s2_name.setText(f"👤 {emp2}")
                cell.lbl_s2_shift.setText(f"{icon2} {st2}-{et2} ({sub2})")
                cell.lbl_s2_shift.setStyleSheet(f"font-size: 9px; color: {color2};")
                cell.slot2_box.setVisible(True)
            else:
                cell.slot2_box.setVisible(False)

            # More label
            if total_shifts > 2:
                cell.lbl_more.setText(f"+{total_shifts - 2} ca nữa (bấm xem)")
                cell.lbl_more.setVisible(True)
            else:
                cell.lbl_more.setVisible(False)

    def open_attendance_history_modal(self, target_date=None):
        target_u_id = self.staff_map.get(self.staff_combo.currentText())
        dialog = AttendanceHistoryDialog(
            parent=self,
            current_profile=self.current_profile,
            target_date=target_date,
            target_user_id=target_u_id
        )
        dialog.exec()

    def open_add_schedule_modal(self):
        dialog = AddScheduleDialog(
            parent=self,
            supabase=self.supabase,
            default_staff_name=self.staff_combo.currentText()
        )
        if dialog.exec() == QDialog.Accepted:
            self._schedule_cache.clear()
            self.render_month_calendar()

    def open_general_leave_modal(self):
        dialog = RequestLeaveDialog(
            parent=self,
            supabase=self.supabase,
            current_profile=self.current_profile
        )
        if dialog.exec() == QDialog.Accepted:
            self._schedule_cache.clear()
            self.render_month_calendar()
