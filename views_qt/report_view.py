from datetime import datetime, date
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QComboBox, QScrollArea, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from core.supabase_service import SupabaseService
from core.qt_worker import QtWorker

class ReportView(QWidget):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent)
        self.current_profile = current_profile or {}
        self.supabase = SupabaseService()
        self.branch_id = self.current_profile.get("branch_id")
        self.user_role = self.current_profile.get("role", "storemanager")
        self.report_data = []
        self.branch_map = {}
        self.worker = None

        self.setup_ui()
        self.load_filters()

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(15)

        # 1. Header & Controls
        filter_card = QFrame()
        filter_card.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 12px; padding: 15px;")
        fc_layout = QVBoxLayout(filter_card)
        fc_layout.setSpacing(12)

        lbl_title = QLabel("📊 BÁO CÁO CHẤM CÔNG & XUẤT EXCEL")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; border: none;")
        fc_layout.addWidget(lbl_title)

        ctrl_row = QWidget()
        ctrl_row.setStyleSheet("border: none;")
        cr_layout = QHBoxLayout(ctrl_row)
        cr_layout.setContentsMargins(0, 0, 0, 0)
        cr_layout.setSpacing(10)

        self.branch_combo = QComboBox()
        self.branch_combo.setFixedWidth(220)
        cr_layout.addWidget(self.branch_combo)

        cur_month = date.today().month
        self.month_combo = QComboBox()
        self.month_combo.setFixedWidth(130)
        for m in range(1, 13):
            self.month_combo.addItem(f"Tháng {m}", m)
        self.month_combo.setCurrentIndex(cur_month - 1)
        cr_layout.addWidget(self.month_combo)

        cur_year = date.today().year
        self.year_combo = QComboBox()
        self.year_combo.setFixedWidth(110)
        for y in [cur_year - 1, cur_year, cur_year + 1]:
            self.year_combo.addItem(str(y), y)
        self.year_combo.setCurrentText(str(cur_year))
        cr_layout.addWidget(self.year_combo)

        self.btn_search = QPushButton("🔍 Tra cứu")
        self.btn_search.setFixedSize(110, 36)
        self.btn_search.setStyleSheet("""
            QPushButton {
                background-color: #1F6AA5; color: white; font-weight: bold;
                border-radius: 8px; border: none; font-size: 13px;
            }
            QPushButton:hover { background-color: #257EC4; }
        """)
        self.btn_search.clicked.connect(self.load_report_data)
        cr_layout.addWidget(self.btn_search)

        cr_layout.addStretch()

        self.btn_export = QPushButton("📥 Xuất File Excel")
        self.btn_export.setFixedSize(150, 36)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #28A745; color: white; font-weight: bold;
                border-radius: 8px; border: none; font-size: 13px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #384F3D; color: #7A9980; }
        """)
        self.btn_export.clicked.connect(self.export_to_excel)
        cr_layout.addWidget(self.btn_export)

        fc_layout.addWidget(ctrl_row)
        root_layout.addWidget(filter_card)

        # 2. KPI Cards Row
        kpi_row = QWidget()
        kr_layout = QHBoxLayout(kpi_row)
        kr_layout.setContentsMargins(0, 0, 0, 0)
        kr_layout.setSpacing(12)

        self.kpi_total = self._create_kpi_card("Tổng ca làm", "0", "#3B8ED0")
        self.kpi_ontime = self._create_kpi_card("Đúng giờ", "0", "#28A745")
        self.kpi_late = self._create_kpi_card("Số lần trễ", "0", "#DC3545")
        self.kpi_late_mins = self._create_kpi_card("Tổng phút trễ", "0 phút", "#FD7E14")

        kr_layout.addWidget(self.kpi_total["frame"])
        kr_layout.addWidget(self.kpi_ontime["frame"])
        kr_layout.addWidget(self.kpi_late["frame"])
        kr_layout.addWidget(self.kpi_late_mins["frame"])
        root_layout.addWidget(kpi_row)

        # 3. Table Summary Area
        self.table_card = QFrame()
        self.table_card.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 12px; padding: 10px;")
        tc_layout = QVBoxLayout(self.table_card)
        tc_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_table = QScrollArea()
        self.scroll_table.setWidgetResizable(True)
        self.content_table = QWidget()
        self.layout_table = QVBoxLayout(self.content_table)
        self.layout_table.setSpacing(6)
        self.scroll_table.setWidget(self.content_table)
        tc_layout.addWidget(self.scroll_table)

        root_layout.addWidget(self.table_card)

    def _create_kpi_card(self, title, val, color):
        frame = QFrame()
        frame.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(3)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; color: gray; border: none;")
        layout.addWidget(lbl_t)

        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color}; border: none;")
        layout.addWidget(lbl_v)

        return {"frame": frame, "val": lbl_v}

    def load_filters(self):
        def fetch():
            return self.supabase.get_branches()

        def on_done(branches):
            if not branches:
                self.branch_combo.addItem("Chưa có chi nhánh")
                return

            self.branch_map = {b.get("name"): b.get("id") for b in branches}
            b_names = list(self.branch_map.keys())

            if self.user_role == "admin":
                self.branch_combo.clear()
                self.branch_combo.addItems(b_names)
            else:
                my_branch_name = [name for name, bid in self.branch_map.items() if bid == self.branch_id]
                if my_branch_name:
                    self.branch_combo.clear()
                    self.branch_combo.addItem(my_branch_name[0])
                    self.branch_combo.setEnabled(False)

        self.worker = QtWorker(fetch)
        self.worker.result_ready.connect(on_done)
        self.worker.start()

    def load_report_data(self):
        b_name = self.branch_combo.currentText()
        target_branch_id = self.branch_map.get(b_name)
        month = self.month_combo.currentData() or date.today().month
        year = int(self.year_combo.currentText())

        while self.layout_table.count():
            item = self.layout_table.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl_loading = QLabel("⏳ Đang truy vấn dữ liệu chấm công từ hệ thống...")
        lbl_loading.setStyleSheet("font-size: 13px; color: gray; padding: 40px;")
        lbl_loading.setAlignment(Qt.AlignCenter)
        self.layout_table.addWidget(lbl_loading)

        self.btn_search.setEnabled(False)
        self.btn_search.setText("Đang nạp...")

        def fetch():
            return self.supabase.get_monthly_attendance_data(target_branch_id, year, month)

        def on_done(schedules):
            self.btn_search.setEnabled(True)
            self.btn_search.setText("🔍 Tra cứu")
            self.report_data = schedules or []
            self._render_report_ui(self.report_data)

        self.worker = QtWorker(fetch)
        self.worker.result_ready.connect(on_done)
        self.worker.start()

    def _render_report_ui(self, schedules):
        while self.layout_table.count():
            item = self.layout_table.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not schedules:
            self.kpi_total["val"].setText("0")
            self.kpi_ontime["val"].setText("0")
            self.kpi_late["val"].setText("0")
            self.kpi_late_mins["val"].setText("0 phút")
            lbl_empty = QLabel("Không có dữ liệu chấm công cho tháng này.")
            lbl_empty.setStyleSheet("font-size: 13px; color: gray; padding: 40px;")
            lbl_empty.setAlignment(Qt.AlignCenter)
            self.layout_table.addWidget(lbl_empty)
            return

        total_shifts = len(schedules)
        total_late = 0
        total_late_mins = 0
        total_ontime = 0
        staff_stats = {}

        for item in schedules:
            profile = item.get("profiles") or {}
            user_id = profile.get("id", "unknown")
            full_name = profile.get("full_name", "Không tên")

            if user_id not in staff_stats:
                staff_stats[user_id] = {
                    "name": full_name,
                    "total": 0,
                    "ontime": 0,
                    "late": 0,
                    "late_mins": 0,
                    "leave": 0
                }

            st = item.get("status")
            if st == "leave":
                staff_stats[user_id]["leave"] += 1
                continue

            staff_stats[user_id]["total"] += 1
            att_list = item.get("attendance") or []
            if att_list:
                att = att_list[0] if isinstance(att_list, list) else att_list
                if att.get("is_late"):
                    total_late += 1
                    mins = att.get("late_minutes", 0)
                    total_late_mins += mins
                    staff_stats[user_id]["late"] += 1
                    staff_stats[user_id]["late_mins"] += mins
                else:
                    total_ontime += 1
                    staff_stats[user_id]["ontime"] += 1

        self.kpi_total["val"].setText(str(total_shifts))
        self.kpi_ontime["val"].setText(str(total_ontime))
        self.kpi_late["val"].setText(str(total_late))
        self.kpi_late_mins["val"].setText(f"{total_late_mins} phút")

        # Header bảng
        head_card = QFrame()
        head_card.setStyleSheet("background-color: #18324F; border-radius: 6px; padding: 6px 12px;")
        h_layout = QHBoxLayout(head_card)
        headers = [("Dược sĩ / Nhân viên", 220), ("Tổng ca", 90), ("Đúng giờ", 90), ("Đi trễ", 90), ("Tổng phút trễ", 110), ("Nghỉ phép", 90)]
        for h, w in headers:
            lbl = QLabel(h)
            lbl.setFixedWidth(w)
            lbl.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 12px; border: none;")
            h_layout.addWidget(lbl)
        h_layout.addStretch()
        self.layout_table.addWidget(head_card)

        # Danh sách dòng nhân viên
        for uid, stat in staff_stats.items():
            row_card = QFrame()
            row_card.setStyleSheet("background-color: #1E1E1E; border: 1px solid #2E2E2E; border-radius: 6px; padding: 6px 12px;")
            r_layout = QHBoxLayout(row_card)

            lbl_n = QLabel(f"💊 {stat['name']}")
            lbl_n.setFixedWidth(220)
            lbl_n.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 12px; border: none;")
            r_layout.addWidget(lbl_n)

            lbl_t = QLabel(str(stat["total"]))
            lbl_t.setFixedWidth(90)
            lbl_t.setStyleSheet("border: none;")
            r_layout.addWidget(lbl_t)

            lbl_o = QLabel(str(stat["ontime"]))
            lbl_o.setFixedWidth(90)
            lbl_o.setStyleSheet("color: #28A745; font-weight: bold; border: none;")
            r_layout.addWidget(lbl_o)

            lbl_l = QLabel(str(stat["late"]))
            lbl_l.setFixedWidth(90)
            lbl_l.setStyleSheet("color: #DC3545; font-weight: bold; border: none;")
            r_layout.addWidget(lbl_l)

            lbl_lm = QLabel(f"{stat['late_mins']} phút")
            lbl_lm.setFixedWidth(110)
            lbl_lm.setStyleSheet("color: #FD7E14; border: none;")
            r_layout.addWidget(lbl_lm)

            lbl_lv = QLabel(str(stat["leave"]))
            lbl_lv.setFixedWidth(90)
            lbl_lv.setStyleSheet("color: #64B5F6; border: none;")
            r_layout.addWidget(lbl_lv)

            r_layout.addStretch()
            self.layout_table.addWidget(row_card)

        self.layout_table.addStretch()

    def export_to_excel(self):
        if not self.report_data:
            QMessageBox.warning(self, "Lưu ý", "Không có dữ liệu để xuất! Vui lòng bấm 'Tra cứu' trước.")
            return

        b_name = self.branch_combo.currentText()
        month = self.month_combo.currentText()
        year = self.year_combo.currentText()

        default_filename = f"Bang_Cham_Cong_{b_name.replace(' ', '_')}_{month.replace(' ', '_')}_{year}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu Bảng Chấm Công Excel", default_filename, "Excel files (*.xlsx)"
        )
        if not file_path:
            return

        self.btn_export.setEnabled(False)
        self.btn_export.setText("Đang xuất file...")

        def export_worker():
            try:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Bảng Chấm Công"

                ws.merge_cells("A1:G1")
                title_cell = ws["A1"]
                title_cell.value = f"BẢNG TỔNG HỢP CHẤM CÔNG - {b_name.upper()} ({month.upper()}/{year})"
                title_cell.font = Font(name="Calibri", size=15, bold=True, color="1F4E78")
                title_cell.alignment = Alignment(horizontal="center", vertical="center")

                headers = ["STT", "Họ và Tên", "Ngày làm việc", "Ca làm", "Check-in", "Check-out", "Đi trễ (Phút)"]
                ws.append([])
                ws.append(headers)

                header_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
                header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
                thin_border = Border(
                    left=Side(style='thin', color='D9D9D9'),
                    right=Side(style='thin', color='D9D9D9'),
                    top=Side(style='thin', color='D9D9D9'),
                    bottom=Side(style='thin', color='D9D9D9')
                )

                for col_idx in range(1, len(headers) + 1):
                    cell = ws.cell(row=3, column=col_idx)
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")

                stt = 1
                for item in self.report_data:
                    profile = item.get("profiles") or {}
                    name = profile.get("full_name", "")
                    w_date = item.get("work_date", "")
                    shift = item.get("shifts") or {}
                    shift_name = f"{shift.get('name', '')} ({shift.get('start_time', '')[:5]}-{shift.get('end_time', '')[:5]})"

                    att_list = item.get("attendance") or []
                    check_in_str = "Chưa"
                    check_out_str = "Chưa"
                    late_mins = 0

                    if att_list:
                        att = att_list[0] if isinstance(att_list, list) else att_list
                        cin = att.get("check_in", "")
                        cout = att.get("check_out", "")
                        check_in_str = cin[11:19] if len(cin) >= 19 else cin
                        check_out_str = cout[11:19] if len(cout) >= 19 else (cout or "Chưa")
                        late_mins = att.get("late_minutes", 0) if att.get("is_late") else 0

                    row_data = [stt, name, w_date, shift_name, check_in_str, check_out_str, late_mins]
                    ws.append(row_data)

                    current_row = ws.max_row
                    for col_idx in range(1, len(headers) + 1):
                        cell = ws.cell(row=current_row, column=col_idx)
                        cell.border = thin_border
                        if col_idx in (1, 3, 5, 6, 7):
                            cell.alignment = Alignment(horizontal="center")
                        if col_idx == 7 and late_mins > 0:
                            cell.font = Font(color="FF0000", bold=True)

                    stt += 1

                for col in ws.columns:
                    max_len = 0
                    col_letter = get_column_letter(col[0].column)
                    for cell in col:
                        if cell.value:
                            max_len = max(max_len, len(str(cell.value)))
                    ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

                wb.save(file_path)
                return True, file_path
            except Exception as e:
                return False, str(e)

        def on_done(res):
            self.btn_export.setEnabled(True)
            self.btn_export.setText("📥 Xuất File Excel")
            ok, msg = res
            if ok:
                QMessageBox.information(self, "Xuất File Thành Công", f"Đã xuất bảng chấm công thành công tại:\n{msg}")
            else:
                QMessageBox.critical(self, "Lỗi", f"Không thể xuất file báo cáo Excel: {msg}")

        self.worker = QtWorker(export_worker)
        self.worker.result_ready.connect(on_done)
        self.worker.start()
