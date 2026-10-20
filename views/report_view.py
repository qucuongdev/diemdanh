import threading
from datetime import datetime, date
import customtkinter as ctk
from tkinter import filedialog, messagebox
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from core.supabase_service import SupabaseService

class ReportView(ctk.CTkFrame):
    def __init__(self, master, current_profile):
        super().__init__(master, fg_color="transparent")
        self.current_profile = current_profile
        self.supabase = SupabaseService()
        self.branch_id = self.current_profile.get("branch_id")
        self.user_role = self.current_profile.get("role", "storemanager")

        self.report_data = []

        self.setup_ui()
        self.load_filters()

    def setup_ui(self):
        # Header & Filter Frame
        self.filter_frame = ctk.CTkFrame(self, fg_color=("white", "#242424"), corner_radius=12)
        self.filter_frame.pack(fill="x", padx=20, pady=(20, 15))

        # Tiêu đề
        self.title_lbl = ctk.CTkLabel(
            self.filter_frame, text="📊 BÁO CÁO CHẤM CÔNG & XUẤT EXCEL",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.title_lbl.pack(anchor="w", padx=20, pady=(15, 10))

        # Controls Row
        self.controls_box = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        self.controls_box.pack(fill="x", padx=20, pady=(0, 15))

        # Branch dropdown (cho Admin)
        self.branch_var = ctk.StringVar(value="Chi nhánh")
        self.branch_menu = ctk.CTkOptionMenu(self.controls_box, variable=self.branch_var, width=200)
        self.branch_menu.pack(side="left", padx=(0, 10))

        # Month dropdown
        cur_month = date.today().month
        self.month_var = ctk.StringVar(value=f"Tháng {cur_month}")
        month_list = [f"Tháng {m}" for m in range(1, 13)]
        self.month_menu = ctk.CTkOptionMenu(self.controls_box, variable=self.month_var, values=month_list, width=120)
        self.month_menu.pack(side="left", padx=(0, 10))

        # Year dropdown
        cur_year = date.today().year
        self.year_var = ctk.StringVar(value=str(cur_year))
        year_list = [str(cur_year - 1), str(cur_year), str(cur_year + 1)]
        self.year_menu = ctk.CTkOptionMenu(self.controls_box, variable=self.year_var, values=year_list, width=100)
        self.year_menu.pack(side="left", padx=(0, 15))

        # Nút Tra cứu
        self.btn_search = ctk.CTkButton(
            self.controls_box, text="🔍 Tra cứu", width=110, height=36,
            fg_color=("#3B8ED0", "#1F6AA5"), command=self.load_report_data
        )
        self.btn_search.pack(side="left", padx=(0, 10))

        # Nút Xuất Excel
        self.btn_export = ctk.CTkButton(
            self.controls_box, text="📥 Xuất File Excel", width=140, height=36,
            fg_color="#28A745", hover_color="#218838", font=ctk.CTkFont(weight="bold"),
            command=self.export_to_excel
        )
        self.btn_export.pack(side="right")

        # KPI Dashboard Cards
        self.kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_frame.pack(fill="x", padx=20, pady=(0, 15))
        self.kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.kpi_total = self.create_kpi_card(self.kpi_frame, 0, "Tổng ca làm", "0", "#3B8ED0")
        self.kpi_ontime = self.create_kpi_card(self.kpi_frame, 1, "Đúng giờ", "0", "#28A745")
        self.kpi_late = self.create_kpi_card(self.kpi_frame, 2, "Số lần trễ", "0", "#DC3545")
        self.kpi_late_mins = self.create_kpi_card(self.kpi_frame, 3, "Tổng phút trễ", "0 phút", "#FD7E14")

        # Table data cuộn được
        self.table_frame = ctk.CTkScrollableFrame(self, fg_color=("white", "#242424"), corner_radius=12)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=0)

    def create_kpi_card(self, parent, col, title, init_val, color):
        card = ctk.CTkFrame(parent, fg_color=("white", "#242424"), corner_radius=10)
        card.grid(row=0, column=col, padx=5, sticky="ew")

        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11), text_color="gray")
        lbl_title.pack(anchor="w", padx=15, pady=(10, 0))

        lbl_val = ctk.CTkLabel(card, text=init_val, font=ctk.CTkFont(size=20, weight="bold"), text_color=color)
        lbl_val.pack(anchor="w", padx=15, pady=(0, 10))
        return lbl_val

    def load_filters(self):
        self.branch_menu.configure(values=["Đang tải chi nhánh..."])
        threading.Thread(target=self._fetch_filters_async, daemon=True).start()

    def _fetch_filters_async(self):
        branches = self.supabase.get_branches()
        try:
            self.after(0, self._apply_filters_ui, branches)
        except Exception:
            pass

    def _apply_filters_ui(self, branches):
        if not branches:
            self.branch_menu.configure(values=["Chưa có chi nhánh"])
            return

        self.branch_map = {b.get("name"): b.get("id") for b in branches}
        b_names = list(self.branch_map.keys())

        if self.user_role == "admin":
            self.branch_menu.configure(values=b_names)
            if b_names and (self.branch_var.get() not in b_names or self.branch_var.get() == "Chi nhánh"):
                self.branch_var.set(b_names[0])
        else:
            # Manager chỉ xem chi nhánh mình
            my_branch_name = [name for name, bid in self.branch_map.items() if bid == self.branch_id]
            if my_branch_name:
                self.branch_menu.configure(values=[my_branch_name[0]], state="disabled")
                self.branch_var.set(my_branch_name[0])

    def load_report_data(self):
        b_name = self.branch_var.get()
        target_branch_id = self.branch_map.get(b_name)
        month_str = self.month_var.get().replace("Tháng ", "").strip()
        try:
            month = int(month_str)
        except ValueError:
            month = date.today().month
        try:
            year = int(self.year_var.get().strip())
        except ValueError:
            year = date.today().year

        # Xóa bảng cũ và hiện thông báo tải
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        loading_lbl = ctk.CTkLabel(self.table_frame, text="⏳ Đang truy vấn dữ liệu chấm công từ hệ thống...", text_color="gray")
        loading_lbl.pack(pady=40)

        self.btn_search.configure(state="disabled", text="Đang nạp...")

        def fetch_worker():
            schedules = self.supabase.get_monthly_attendance_data(target_branch_id, year, month)
            try:
                self.after(0, self._render_report_ui, schedules)
            except Exception:
                pass

        threading.Thread(target=fetch_worker, daemon=True).start()

    def _render_report_ui(self, schedules):
        self.btn_search.configure(state="normal", text="🔍 Tra cứu")
        self.report_data = schedules or []

        # Xóa bảng cũ
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        if not schedules:
            self.kpi_total.configure(text="0")
            self.kpi_ontime.configure(text="0")
            self.kpi_late.configure(text="0")
            self.kpi_late_mins.configure(text="0 phút")
            lbl = ctk.CTkLabel(self.table_frame, text="Không có dữ liệu chấm công cho tháng này.", text_color="gray")
            lbl.pack(pady=40)
            return

        # Thống kê tổng quan
        total_shifts = len(schedules)
        total_late = 0
        total_late_mins = 0
        total_ontime = 0

        # Thống kê theo nhân viên: {user_id: {name, total, ontime, late, late_mins, leave}}
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
            else:
                pass

        # Cập nhật KPI cards
        self.kpi_total.configure(text=str(total_shifts))
        self.kpi_ontime.configure(text=str(total_ontime))
        self.kpi_late.configure(text=str(total_late))
        self.kpi_late_mins.configure(text=f"{total_late_mins} phút")

        # Vẽ Header bảng
        headers = ["Dược sĩ / Nhân viên", "Tổng ca", "Đúng giờ", "Đi trễ", "Tổng phút trễ", "Nghỉ phép"]
        head_row = ctk.CTkFrame(self.table_frame, fg_color=("#E5F2FF", "#18324F"), height=36, corner_radius=6)
        head_row.pack(fill="x", padx=5, pady=(5, 5))

        for idx, h in enumerate(headers):
            w = 200 if idx == 0 else 90
            lbl = ctk.CTkLabel(head_row, text=h, font=ctk.CTkFont(size=12, weight="bold"), width=w, anchor="w" if idx == 0 else "center")
            lbl.pack(side="left", padx=10, pady=8)

        # Vẽ từng dòng nhân viên
        for uid, stat in staff_stats.items():
            row = ctk.CTkFrame(self.table_frame, fg_color=("#F9F9F9", "#1E1E1E"), corner_radius=6)
            row.pack(fill="x", padx=5, pady=3)

            ctk.CTkLabel(row, text=f"💊 {stat['name']}", font=ctk.CTkFont(size=12, weight="bold"), width=200, anchor="w").pack(side="left", padx=10, pady=8)
            ctk.CTkLabel(row, text=str(stat["total"]), width=90).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=str(stat["ontime"]), text_color="#28A745", width=90).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=str(stat["late"]), text_color="#DC3545", width=90).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=f"{stat['late_mins']} phút", text_color="#FD7E14", width=90).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=str(stat["leave"]), text_color="#3B8ED0", width=90).pack(side="left", padx=10)

    def export_to_excel(self):
        if not self.report_data:
            messagebox.showwarning("Lưu ý", "Không có dữ liệu để xuất! Vui lòng bấm 'Tra cứu' trước.")
            return

        b_name = self.branch_var.get()
        month = self.month_var.get()
        year = self.year_var.get()

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"Bang_Cham_Cong_{b_name.replace(' ', '_')}_{month.replace(' ', '_')}_{year}.xlsx",
            title="Lưu Bảng Chấm Công Excel"
        )
        if not file_path:
            return

        self.btn_export.configure(state="disabled", text="Đang xuất file...")

        def export_worker():
            try:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Bảng Chấm Công"

                # Tiêu đề báo cáo
                ws.merge_cells("A1:G1")
                title_cell = ws["A1"]
                title_cell.value = f"BẢNG TỔNG HỢP CHẤM CÔNG - {b_name.upper()} ({month.upper()}/{year})"
                title_cell.font = Font(name="Calibri", size=15, bold=True, color="1F4E78")
                title_cell.alignment = Alignment(horizontal="center", vertical="center")

                # Header bảng
                headers = ["STT", "Họ và Tên", "Ngày làm việc", "Ca làm", "Check-in", "Check-out", "Đi trễ (Phút)"]
                ws.append([]) # Dòng 2 trống
                ws.append(headers) # Dòng 3

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

                # Dữ liệu chi tiết từng ca
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

                    # Format border & alignment
                    current_row = ws.max_row
                    for col_idx in range(1, len(headers) + 1):
                        cell = ws.cell(row=current_row, column=col_idx)
                        cell.border = thin_border
                        if col_idx in (1, 3, 5, 6, 7):
                            cell.alignment = Alignment(horizontal="center")
                        if col_idx == 7 and late_mins > 0:
                            cell.font = Font(color="FF0000", bold=True)

                    stt += 1

                # Auto fit column widths
                for col in ws.columns:
                    max_len = 0
                    col_letter = get_column_letter(col[0].column)
                    for cell in col:
                        if cell.value:
                            max_len = max(max_len, len(str(cell.value)))
                    ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

                wb.save(file_path)
                self.after(0, self._on_export_done, True, file_path)
            except Exception as e:
                print(f"[SECURITY/LOG] Lỗi xuất Excel: {e}")
                self.after(0, self._on_export_done, False, str(e))

        threading.Thread(target=export_worker, daemon=True).start()

    def _on_export_done(self, success, result_msg):
        self.btn_export.configure(state="normal", text="📥 Xuất File Excel")
        if success:
            messagebox.showinfo("Xuất File Thành Công", f"Đã xuất bảng chấm công thành công tại:\n{result_msg}")
        else:
            messagebox.showerror("Thông báo", "Không thể xuất file báo cáo Excel. Vui lòng kiểm tra quyền lưu file hoặc đóng file đang mở trước khi xuất lại!")
