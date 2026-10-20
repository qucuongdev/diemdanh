from datetime import datetime, date
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from core.supabase_service import SupabaseService
from core.qt_worker import QtWorker

class AttendanceHistoryDialog(QDialog):
    def __init__(self, parent=None, current_profile=None, target_date=None, target_user_id=None):
        super().__init__(parent)
        self.current_profile = current_profile or {}
        self.supabase = SupabaseService()
        self.user_role = self.current_profile.get("role", "staff")
        self.my_branch_id = self.current_profile.get("branch_id")

        self.target_date = target_date
        self.target_user_id = target_user_id

        self.branches = []
        self.branch_map = {}
        self.staffs = []
        self.staff_map = {}
        self.worker = None

        self.setup_window()
        self.setup_ui()
        self.load_metadata_and_data()

    def setup_window(self):
        self.setWindowTitle("Lịch Sử Check-in & Check-out Chi Tiết")
        self.resize(1020, 680)
        self.setMinimumSize(850, 550)
        self.setStyleSheet("""
            QDialog {
                background-color: #1A1A1A;
            }
        """)

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(15, 15, 15, 15)
        root_layout.setSpacing(10)

        # 1. Header Frame
        header = QFrame()
        header.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px; padding: 10px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(15, 5, 15, 5)

        lbl_title = QLabel("📋 NHẬT KÝ & LỊCH SỬ CHECK-IN / CHECK-OUT")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4285F4; border: none;")
        h_layout.addWidget(lbl_title)

        h_layout.addStretch()

        btn_close = QPushButton("✕ Đóng")
        btn_close.setFixedSize(75, 30)
        btn_close.setStyleSheet("background-color: #333333; color: white; border: none; border-radius: 6px; font-weight: bold;")
        btn_close.clicked.connect(self.close)
        h_layout.addWidget(btn_close)

        root_layout.addWidget(header)

        # 2. Filter Bar
        filter_box = QFrame()
        filter_box.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px; padding: 6px 12px;")
        f_layout = QHBoxLayout(filter_box)
        f_layout.setSpacing(10)

        f_layout.addWidget(QLabel("Ngày:"))
        self.date_entry = QLineEdit()
        self.date_entry.setPlaceholderText("YYYY-MM-DD")
        self.date_entry.setFixedWidth(110)
        if self.target_date:
            self.date_entry.setText(str(self.target_date))
        f_layout.addWidget(self.date_entry)

        btn_today = QPushButton("Hôm nay")
        btn_today.setFixedSize(75, 30)
        btn_today.setStyleSheet("background-color: #1F6AA5; color: white; border-radius: 6px; font-weight: bold;")
        btn_today.clicked.connect(self.set_today_filter)
        f_layout.addWidget(btn_today)

        btn_all_dates = QPushButton("Tất cả ngày")
        btn_all_dates.setFixedSize(85, 30)
        btn_all_dates.setStyleSheet("background-color: #333333; color: white; border-radius: 6px;")
        btn_all_dates.clicked.connect(self.clear_date_filter)
        f_layout.addWidget(btn_all_dates)

        f_layout.addWidget(QLabel("Nhân sự:"))
        self.staff_combo = QComboBox()
        self.staff_combo.setFixedWidth(170)
        f_layout.addWidget(self.staff_combo)

        f_layout.addWidget(QLabel("Chi nhánh:"))
        self.branch_combo = QComboBox()
        self.branch_combo.setFixedWidth(160)
        f_layout.addWidget(self.branch_combo)

        btn_search = QPushButton("🔍 Tra cứu")
        btn_search.setFixedSize(90, 30)
        btn_search.setStyleSheet("background-color: #28A745; color: white; border-radius: 6px; font-weight: bold;")
        btn_search.clicked.connect(self.load_data)
        f_layout.addWidget(btn_search)

        f_layout.addStretch()
        root_layout.addWidget(filter_box)

        # 3. KPI Summary Row
        kpi_box = QWidget()
        kpi_layout = QHBoxLayout(kpi_box)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(10)

        self.kpi_total = self._create_kpi_card("Tổng số lượt", "0 lượt", "#4285F4")
        self.kpi_ontime = self._create_kpi_card("Đúng giờ", "0 lượt", "#28A745")
        self.kpi_late = self._create_kpi_card("Vào muộn", "0 lượt", "#FD7E14")
        self.kpi_early = self._create_kpi_card("Về sớm / Đang ca", "0 lượt", "#9C27B0")

        kpi_layout.addWidget(self.kpi_total["frame"])
        kpi_layout.addWidget(self.kpi_ontime["frame"])
        kpi_layout.addWidget(self.kpi_late["frame"])
        kpi_layout.addWidget(self.kpi_early["frame"])
        root_layout.addWidget(kpi_box)

        # 4. Scrollable Records Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.list_layout = QVBoxLayout(self.scroll_content)
        self.list_layout.setSpacing(8)
        self.scroll_area.setWidget(self.scroll_content)
        root_layout.addWidget(self.scroll_area)

    def _create_kpi_card(self, title, val, color):
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #242424; border: 1px solid #333333; border-radius: 8px;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; color: gray; border: none;")
        layout.addWidget(lbl_t)

        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color}; border: none;")
        layout.addWidget(lbl_v)

        return {"frame": frame, "val": lbl_v}

    def set_today_filter(self):
        self.date_entry.setText(date.today().isoformat())
        self.load_data()

    def clear_date_filter(self):
        self.date_entry.clear()
        self.load_data()

    def load_metadata_and_data(self):
        def fetch_meta():
            b = self.supabase.get_branches()
            s = self.supabase.get_staff_list()
            return b, s

        def on_meta_loaded(data):
            branches, staffs = data
            self.branches = branches or []
            self.branch_map = {b["name"]: b["id"] for b in self.branches}
            b_names = ["Tất cả chi nhánh"] + list(self.branch_map.keys())
            self.branch_combo.clear()
            self.branch_combo.addItems(b_names)

            self.staffs = staffs or []
            self.staff_map = {st["full_name"]: st["id"] for st in self.staffs}
            staff_names = list(self.staff_map.keys())

            if self.user_role == "staff":
                my_name = self.current_profile.get("full_name")
                self.staff_combo.clear()
                self.staff_combo.addItem(my_name)
                self.staff_combo.setEnabled(False)
                self.branch_combo.setEnabled(False)
            else:
                self.staff_combo.clear()
                self.staff_combo.addItems(["Tất cả nhân viên"] + staff_names)
                if self.target_user_id:
                    for name, uid in self.staff_map.items():
                        if uid == self.target_user_id:
                            self.staff_combo.setCurrentText(name)
                            break

            self.load_data()

        self.worker = QtWorker(fetch_meta)
        self.worker.result_ready.connect(on_meta_loaded)
        self.worker.start()

    def load_data(self):
        # Dọn sạch danh sách cũ
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl_loading = QLabel("⏳ Đang tải dữ liệu lịch sử chấm công...")
        lbl_loading.setStyleSheet("font-size: 13px; color: gray; padding: 40px;")
        lbl_loading.setAlignment(Qt.AlignCenter)
        self.list_layout.addWidget(lbl_loading)

        raw_date = self.date_entry.text().strip()
        date_param = raw_date if raw_date else None

        user_param = None
        selected_staff = self.staff_combo.currentText()
        if selected_staff and selected_staff != "Tất cả nhân viên":
            user_param = self.staff_map.get(selected_staff)
        elif self.user_role == "staff":
            user_param = self.current_profile.get("id")

        b_name = self.branch_combo.currentText()
        branch_param = self.branch_map.get(b_name)
        if self.user_role != "admin" and not branch_param:
            branch_param = self.my_branch_id

        def query_records():
            res = self.supabase.client.from_("attendance").select("""
                id, check_in, check_out, is_late, late_minutes, early_minutes, status, note,
                schedules (
                    id, work_date,
                    shifts (name, start_time, end_time),
                    branches (name)
                ),
                profiles (id, full_name, role)
            """).order("check_in", desc=True)

            if date_param:
                res = res.gte("check_in", f"{date_param}T00:00:00").lte("check_in", f"{date_param}T23:59:59")
            if user_param:
                res = res.eq("user_id", user_param)

            data = res.execute().data or []
            if branch_param:
                filtered = []
                for item in data:
                    sched = item.get("schedules") or {}
                    b_info = sched.get("branches") or {}
                    if b_info.get("name") == b_name:
                        filtered.append(item)
                return filtered
            return data

        def on_records_loaded(records):
            while self.list_layout.count():
                item = self.list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            self._render_records(records)

        self.worker = QtWorker(query_records)
        self.worker.result_ready.connect(on_records_loaded)
        self.worker.start()

    def _render_records(self, records):
        if not records:
            lbl_empty = QLabel("Không tìm thấy bản ghi chấm công nào phù hợp.")
            lbl_empty.setStyleSheet("font-size: 13px; color: gray; padding: 40px;")
            lbl_empty.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(lbl_empty)
            self.kpi_total["val"].setText("0 lượt")
            self.kpi_ontime["val"].setText("0 lượt")
            self.kpi_late["val"].setText("0 lượt")
            self.kpi_early["val"].setText("0 lượt")
            return

        cnt_total = len(records)
        cnt_ontime = 0
        cnt_late = 0
        cnt_early = 0

        for r in records:
            prof = r.get("profiles") or {}
            sched = r.get("schedules") or {}
            shift = sched.get("shifts") or {}
            branch = sched.get("branches") or {}

            staff_name = prof.get("full_name", "Nhân viên")
            branch_name = branch.get("name", "Chi nhánh")
            shift_name = f"{shift.get('name', 'Ca làm')} ({shift.get('start_time', '')[:5]}-{shift.get('end_time', '')[:5]})"

            cin = r.get("check_in", "")
            cout = r.get("check_out", "")
            is_late = r.get("is_late", False)
            late_min = r.get("late_minutes", 0)

            cin_str = cin[11:19] if len(cin) >= 19 else (cin or "Chưa")
            cout_str = cout[11:19] if len(cout) >= 19 else (cout or "Chưa check-out")
            work_date = cin[:10] if len(cin) >= 10 else sched.get("work_date", "")

            if is_late:
                cnt_late += 1
            else:
                cnt_ontime += 1

            if not cout:
                cnt_early += 1

            # Card dòng lịch sử
            card = QFrame()
            card.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 8px; padding: 10px;")
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(12, 8, 12, 8)

            left = QVBoxLayout()
            left.setSpacing(3)
            lbl_staff = QLabel(f"👤 {staff_name}  •  🏥 {branch_name}  •  📅 {work_date}")
            lbl_staff.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF; border: none;")
            left.addWidget(lbl_staff)

            lbl_detail = QLabel(f"⏰ {shift_name}  |  Vào ca: {cin_str}  →  Tan ca: {cout_str}")
            lbl_detail.setStyleSheet("font-size: 12px; color: #CCCCCC; border: none;")
            left.addWidget(lbl_detail)
            c_layout.addLayout(left)

            c_layout.addStretch()

            # Status Badge
            badge = QLabel()
            if is_late:
                badge.setText(f"⚠️ Trễ {late_min} phút")
                badge.setStyleSheet("background-color: #553310; color: #FD7E14; padding: 4px 10px; border-radius: 6px; font-weight: bold; border: none;")
            else:
                badge.setText("✅ Đúng giờ")
                badge.setStyleSheet("background-color: #1E3D25; color: #28A745; padding: 4px 10px; border-radius: 6px; font-weight: bold; border: none;")
            c_layout.addWidget(badge)

            self.list_layout.addWidget(card)

        self.kpi_total["val"].setText(f"{cnt_total} lượt")
        self.kpi_ontime["val"].setText(f"{cnt_ontime} lượt")
        self.kpi_late["val"].setText(f"{cnt_late} lượt")
        self.kpi_early["val"].setText(f"{cnt_early} lượt")
        self.list_layout.addStretch()
