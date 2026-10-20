import threading
from datetime import datetime, date
import customtkinter as ctk
from core.supabase_service import SupabaseService

class AttendanceHistoryModal(ctk.CTkToplevel):
    def __init__(self, master, current_profile, target_date=None, target_user_id=None):
        super().__init__(master)
        self.current_profile = current_profile
        self.supabase = SupabaseService()
        self.user_role = self.current_profile.get("role", "staff")
        self.my_branch_id = self.current_profile.get("branch_id")
        
        self.target_date = target_date
        self.target_user_id = target_user_id

        self.branches = []
        self.branch_map = {}
        self.staffs = []
        self.staff_map = {}
        self.records = []

        self.setup_window()
        self.setup_ui()
        self.load_metadata_and_data()

    def setup_window(self):
        self.title("Lịch Sử Check-in & Check-out Chi Tiết")
        self.geometry("1020x680")
        self.minsize(850, 550)
        
        # Căn giữa cửa sổ so với master
        try:
            self.transient(self.master.winfo_toplevel())
            self.grab_set()
        except Exception:
            pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

    def setup_ui(self):
        # ================= 1. HEADER =================
        self.header_frame = ctk.CTkFrame(self, fg_color=("white", "#242424"), corner_radius=12)
        self.header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(fill="x", padx=20, pady=12)

        ctk.CTkLabel(
            title_box, 
            text="📋 NHẬT KÝ & LỊCH SỬ CHECK-IN / CHECK-OUT", 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#1A73E8", "#4285F4")
        ).pack(side="left")

        self.btn_close = ctk.CTkButton(
            title_box, text="✕ Đóng", width=75, height=30,
            fg_color="transparent", border_width=1, hover_color=("#E0E0E0", "#333333"),
            command=self.destroy
        )
        self.btn_close.pack(side="right")

        # ================= 2. BỘ LỌC TÌM KIẾM =================
        self.filter_frame = ctk.CTkFrame(self, fg_color=("white", "#242424"), corner_radius=12)
        self.filter_frame.pack(fill="x", padx=15, pady=(0, 10))

        filter_row = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        filter_row.pack(fill="x", padx=15, pady=10)

        # Lọc Ngày
        ctk.CTkLabel(filter_row, text="Ngày:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 5))
        self.date_entry = ctk.CTkEntry(filter_row, width=120, height=32, placeholder_text="YYYY-MM-DD")
        if self.target_date:
            self.date_entry.insert(0, str(self.target_date))
        self.date_entry.pack(side="left", padx=(0, 6))

        self.btn_today = ctk.CTkButton(
            filter_row, text="Hôm nay", width=75, height=32,
            fg_color=("#3B8ED0", "#1F6AA5"), command=self.set_today_filter
        )
        self.btn_today.pack(side="left", padx=(0, 6))

        self.btn_all_dates = ctk.CTkButton(
            filter_row, text="Tất cả ngày", width=85, height=32,
            fg_color="transparent", border_width=1, command=self.clear_date_filter
        )
        self.btn_all_dates.pack(side="left", padx=(0, 15))

        # Lọc Nhân viên
        ctk.CTkLabel(filter_row, text="Nhân sự:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 5))
        self.staff_var = ctk.StringVar(value="Tất cả nhân viên")
        self.staff_menu = ctk.CTkOptionMenu(
            filter_row, variable=self.staff_var, width=190, height=32,
            command=lambda _: self.load_data()
        )
        self.staff_menu.pack(side="left", padx=(0, 15))

        # Lọc Chi nhánh
        ctk.CTkLabel(filter_row, text="Chi nhánh:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 5))
        self.branch_var = ctk.StringVar(value="Tất cả chi nhánh")
        self.branch_menu = ctk.CTkOptionMenu(
            filter_row, variable=self.branch_var, width=170, height=32,
            command=lambda _: self.load_data()
        )
        self.branch_menu.pack(side="left", padx=(0, 15))

        # Nút Tra cứu
        self.btn_search = ctk.CTkButton(
            filter_row, text="🔍 Tra cứu", width=95, height=32,
            fg_color="#28A745", hover_color="#218838", font=ctk.CTkFont(weight="bold"),
            command=self.load_data
        )
        self.btn_search.pack(side="left")

        # ================= 3. THANH THỐNG KÊ KPI NHANH =================
        self.kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_frame.pack(fill="x", padx=15, pady=(0, 10))
        self.kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.kpi_total = self.create_kpi_card(self.kpi_frame, 0, "Tổng số lượt", "0 lượt", "#1A73E8")
        self.kpi_ontime = self.create_kpi_card(self.kpi_frame, 1, "Đúng giờ", "0 lượt", "#28A745")
        self.kpi_late = self.create_kpi_card(self.kpi_frame, 2, "Vào muộn", "0 lượt", "#FD7E14")
        self.kpi_early = self.create_kpi_card(self.kpi_frame, 3, "Về sớm / Đang ca", "0 lượt", "#6F42C1")

        # ================= 4. DANH SÁCH BẢNG LỊCH SỬ (SCROLLABLE) =================
        self.scroll_list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def create_kpi_card(self, parent, col, title, value, color):
        card = ctk.CTkFrame(parent, fg_color=("white", "#242424"), corner_radius=10, height=65)
        card.grid(row=0, column=col, padx=4, sticky="ew")
        card.pack_propagate(False)

        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11), text_color="gray")
        lbl_title.pack(pady=(8, 0))

        lbl_val = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=15, weight="bold"), text_color=color)
        lbl_val.pack(pady=(2, 8))
        return lbl_val

    def set_today_filter(self):
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, date.today().isoformat())
        self.load_data()

    def clear_date_filter(self):
        self.date_entry.delete(0, "end")
        self.load_data()

    def load_metadata_and_data(self):
        # 1. Chi nhánh
        self.branches = self.supabase.get_branches()
        self.branch_map = {b["name"]: b["id"] for b in self.branches}
        b_names = ["Tất cả chi nhánh"] + list(self.branch_map.keys())
        self.branch_menu.configure(values=b_names)

        # 2. Nhân sự
        self.staffs = self.supabase.get_staff_list()
        self.staff_map = {s["full_name"]: s["id"] for s in self.staffs}
        staff_names = list(self.staff_map.keys())

        if self.user_role == "staff":
            my_name = self.current_profile.get("full_name")
            self.staff_var.set(my_name)
            self.staff_menu.configure(values=[my_name], state="disabled")
            self.branch_menu.configure(state="disabled")
        else:
            self.staff_menu.configure(values=["Tất cả nhân viên"] + staff_names)
            if self.target_user_id:
                # Tìm tên nhân viên tương ứng
                for name, uid in self.staff_map.items():
                    if uid == self.target_user_id:
                        self.staff_var.set(name)
                        break

        self.load_data()

    def load_data(self):
        # Hiển thị trạng thái đang tải
        for w in self.scroll_list.winfo_children():
            w.destroy()
        
        lbl_loading = ctk.CTkLabel(
            self.scroll_list, text="⏳ Đang tải dữ liệu lịch sử chấm công...", 
            font=ctk.CTkFont(size=14), text_color="gray"
        )
        lbl_loading.pack(pady=40)

        # Đọc tham số lọc
        raw_date = self.date_entry.get().strip()
        date_param = raw_date if raw_date else None

        user_param = None
        selected_staff = self.staff_var.get()
        if selected_staff and selected_staff != "Tất cả nhân viên":
            user_param = self.staff_map.get(selected_staff)
        elif self.user_role == "staff":
            user_param = self.current_profile.get("id")

        branch_param = None
        selected_branch = self.branch_var.get()
        if selected_branch and selected_branch != "Tất cả chi nhánh":
            branch_param = self.branch_map.get(selected_branch)
        elif self.user_role == "storemanager" and self.my_branch_id:
            branch_param = self.my_branch_id

        # Chạy tải ngầm qua Threading
        threading.Thread(
            target=self._fetch_history_thread,
            args=(branch_param, user_param, date_param),
            daemon=True
        ).start()

    def _fetch_history_thread(self, branch_id, user_id, date_str):
        records = self.supabase.get_attendance_history(
            branch_id=branch_id,
            user_id=user_id,
            date_str=date_str,
            limit=150
        )
        try:
            self.after(0, self._render_records, records)
        except Exception:
            pass

    def _render_records(self, records):
        for w in self.scroll_list.winfo_children():
            w.destroy()

        self.records = records

        # Cập nhật KPI
        total = len(records)
        ontime = sum(1 for r in records if not r.get("is_late"))
        late = sum(1 for r in records if r.get("is_late"))
        early_or_inshift = sum(1 for r in records if r.get("is_early_leave") or not r.get("check_out"))

        self.kpi_total.configure(text=f"{total} lượt")
        self.kpi_ontime.configure(text=f"{ontime} lượt")
        self.kpi_late.configure(text=f"{late} lượt")
        self.kpi_early.configure(text=f"{early_or_inshift} lượt")

        if not records:
            empty_frame = ctk.CTkFrame(self.scroll_list, fg_color=("white", "#242424"), corner_radius=12)
            empty_frame.pack(fill="x", pady=30, padx=10)
            ctk.CTkLabel(
                empty_frame, 
                text="Chưa có lượt Check-in / Check-out nào phù hợp với bộ lọc.", 
                font=ctk.CTkFont(size=14), text_color="gray"
            ).pack(pady=30)
            return

        # Hiển thị từng bản ghi chấm công dạng Card đẹp mắt
        for rec in records:
            self.create_record_card(rec)

    def create_record_card(self, rec):
        prof = rec.get("profiles") or {}
        emp_name = prof.get("full_name") or "Chưa rõ"
        emp_role = prof.get("role", "staff")
        emp_phone = prof.get("phone") or ""

        sched = rec.get("schedules") or {}
        work_date = sched.get("work_date") or rec.get("created_at", "")[:10]
        shift = sched.get("shifts") or {}
        shift_name = shift.get("name") or "Ca làm việc"
        st = shift.get("start_time", "")[:5]
        et = shift.get("end_time", "")[:5]

        branch = rec.get("branches") or {}
        branch_name = branch.get("name") or "Chi nhánh quầy"

        cin = rec.get("check_in")
        cout = rec.get("check_out")

        cin_str = cin[11:19] if cin and len(cin) >= 19 else (cin[11:16] if cin else "--:--")
        cout_str = cout[11:19] if cout and len(cout) >= 19 else (cout[11:16] if cout else "ĐANG TRONG CA")

        is_late = rec.get("is_late", False)
        late_min = rec.get("late_minutes", 0)
        is_early = rec.get("is_early_leave", False)
        early_min = rec.get("early_minutes", 0)

        # Tính thời lượng làm việc thực tế
        duration_str = "--"
        if cin and cout:
            try:
                # Bỏ timezone nếu có
                c_in_clean = cin[:19]
                c_out_clean = cout[:19]
                t_in = datetime.fromisoformat(c_in_clean)
                t_out = datetime.fromisoformat(c_out_clean)
                diff = t_out - t_in
                tot_seconds = int(diff.total_seconds())
                if tot_seconds > 0:
                    hrs = tot_seconds // 3600
                    mins = (tot_seconds % 3600) // 60
                    duration_str = f"{hrs}h {mins:02d}p"
            except Exception:
                duration_str = "--"
        elif cin and not cout:
            duration_str = "Đang diễn ra"

        # Khung thẻ Card
        card = ctk.CTkFrame(self.scroll_list, fg_color=("white", "#242424"), corner_radius=10)
        card.pack(fill="x", pady=4, padx=5)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=10)
        inner.grid_columnconfigure(0, weight=2)
        inner.grid_columnconfigure(1, weight=2)
        inner.grid_columnconfigure(2, weight=3)
        inner.grid_columnconfigure(3, weight=2)

        # Cột 1: Thông tin nhân viên & Chi nhánh
        col1 = ctk.CTkFrame(inner, fg_color="transparent")
        col1.grid(row=0, column=0, sticky="w")

        lbl_emp = ctk.CTkLabel(
            col1, text=f"👤 {emp_name}", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("#1A73E8", "#4285F4")
        )
        lbl_emp.pack(anchor="w")

        role_vn = "Chủ chuỗi (Admin)" if emp_role == "admin" else ("Quản lý CN" if emp_role == "storemanager" else "Dược sĩ quầy")
        lbl_sub = ctk.CTkLabel(
            col1, text=f"{role_vn} • 🏥 {branch_name}",
            font=ctk.CTkFont(size=11), text_color="gray"
        )
        lbl_sub.pack(anchor="w")

        # Cột 2: Ngày & Ca phân công
        col2 = ctk.CTkFrame(inner, fg_color="transparent")
        col2.grid(row=0, column=1, sticky="w", padx=10)

        # Định dạng ngày DD/MM/YYYY
        date_display = work_date
        try:
            d_parts = work_date.split("-")
            if len(d_parts) == 3:
                date_display = f"{d_parts[2]}/{d_parts[1]}/{d_parts[0]}"
        except Exception:
            pass

        lbl_date = ctk.CTkLabel(
            col2, text=f"📅 Ngày {date_display}",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl_date.pack(anchor="w")

        lbl_shift = ctk.CTkLabel(
            col2, text=f"⏰ {shift_name} ({st} - {et})",
            font=ctk.CTkFont(size=11), text_color="gray"
        )
        lbl_shift.pack(anchor="w")

        # Cột 3: Giờ Check-in & Check-out thực tế
        col3 = ctk.CTkFrame(inner, fg_color="transparent")
        col3.grid(row=0, column=2, sticky="w", padx=10)

        cin_color = "#FD7E14" if is_late else "#28A745"
        lbl_cin = ctk.CTkLabel(
            col3, 
            text=f"🟢 Vào ca: {cin_str} {'(Muộn ' + str(late_min) + 'p)' if is_late else '(Đúng giờ)'}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=cin_color
        )
        lbl_cin.pack(anchor="w")

        cout_color = "#FD7E14" if is_early else ("#28A745" if cout else "#17A2B8")
        cout_extra = f"(Sớm {early_min}p)" if is_early else ""
        lbl_cout = ctk.CTkLabel(
            col3,
            text=f"🏁 Tan ca: {cout_str} {cout_extra}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=cout_color
        )
        lbl_cout.pack(anchor="w")

        # Cột 4: Tổng giờ làm & Huy hiệu trạng thái
        col4 = ctk.CTkFrame(inner, fg_color="transparent")
        col4.grid(row=0, column=3, sticky="e")

        ctk.CTkLabel(
            col4, text=f"⏱ Công: {duration_str}",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="e")

        # Trạng thái tổng hợp
        if not cout:
            badge_text = "🔵 Đang trong ca"
            badge_fg = ("#E5F2FF", "#18324F")
            badge_tc = "#1A73E8"
        elif is_late:
            badge_text = f"🟠 Vào muộn {late_min}p"
            badge_fg = ("#FFF3CD", "#332701")
            badge_tc = "#D39E00"
        elif is_early:
            badge_text = f"🟡 Về sớm {early_min}p"
            badge_fg = ("#FFF3CD", "#332701")
            badge_tc = "#D39E00"
        else:
            badge_text = "🟢 Chuẩn công"
            badge_fg = ("#D4EDDA", "#155724")
            badge_tc = "#28A745"

        badge = ctk.CTkLabel(
            col4, text=badge_text,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=badge_fg, text_color=badge_tc,
            corner_radius=6, padx=8, pady=2
        )
        badge.pack(anchor="e", pady=(4, 0))
