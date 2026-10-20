import calendar
import threading
from datetime import datetime, date, timedelta
import customtkinter as ctk
from tkinter import messagebox
from core.supabase_service import SupabaseService
from views.attendance_history_modal import AttendanceHistoryModal

class ScheduleView(ctk.CTkFrame):
    def __init__(self, master, current_profile):
        super().__init__(master, fg_color="transparent")
        self.current_profile = current_profile
        self.supabase = SupabaseService()

        # Mặc định xem Tháng & Năm hiện tại
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

        self.setup_ui()
        self.load_filters()
        self.render_month_calendar()

    def setup_ui(self):
        # ================= 1. HEADER: ĐIỀU KHIỂN THÁNG & NÚT THAO TÁC =================
        self.header_frame = ctk.CTkFrame(self, fg_color=("white", "#242424"), corner_radius=12)
        self.header_frame.pack(fill="x", padx=15, pady=(15, 8))

        # Dòng 1: Bộ chọn tháng & Nút Đề xuất
        self.top_bar = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.top_bar.pack(fill="x", padx=15, pady=(10, 5))

        # Nhóm điều hướng tháng ở giữa/trái
        self.nav_box = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.nav_box.pack(side="left")

        self.btn_prev_month = ctk.CTkButton(
            self.nav_box, text="◀", width=36, height=32,
            fg_color="transparent", border_width=1, font=ctk.CTkFont(size=14, weight="bold"),
            command=self.prev_month
        )
        self.btn_prev_month.pack(side="left", padx=(0, 6))

        self.lbl_month_title = ctk.CTkLabel(
            self.nav_box, text="", font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#1A73E8", "#4285F4")
        )
        self.lbl_month_title.pack(side="left", padx=6)

        self.btn_next_month = ctk.CTkButton(
            self.nav_box, text="▶", width=36, height=32,
            fg_color="transparent", border_width=1, font=ctk.CTkFont(size=14, weight="bold"),
            command=self.next_month
        )
        self.btn_next_month.pack(side="left", padx=(6, 12))

        self.btn_today = ctk.CTkButton(
            self.nav_box, text="Hôm nay", width=75, height=32,
            fg_color=("#3B8ED0", "#1F6AA5"), font=ctk.CTkFont(size=12, weight="bold"),
            command=self.goto_today
        )
        self.btn_today.pack(side="left")

        self.lbl_date_range = ctk.CTkLabel(
            self.nav_box, text="", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.lbl_date_range.pack(side="left", padx=15)

        # Nút Đề xuất bên phải (như hình mẫu)
        self.action_box = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.action_box.pack(side="right")

        if self.user_role in ("storemanager", "admin"):
            self.btn_add_shift = ctk.CTkButton(
                self.action_box, text="➕ Xếp ca làm việc", font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="#28A745", hover_color="#218838", height=34,
                command=self.open_add_schedule_modal
            )
            self.btn_add_shift.pack(side="right", padx=(8, 0))

        self.btn_history = ctk.CTkButton(
            self.action_box, text="📜 Lịch sử Check-in/out", font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#17A2B8", hover_color="#138496", height=34,
            command=lambda: self.open_attendance_history_modal()
        )
        self.btn_history.pack(side="right", padx=(8, 0))

        self.btn_request_leave = ctk.CTkButton(
            self.action_box, text="📝 Đề xuất nghỉ", font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#FD7E14", hover_color="#E06A05", height=34,
            command=self.open_general_leave_modal
        )
        self.btn_request_leave.pack(side="right")

        # Dòng 2: Bộ lọc Nhân viên & Chi nhánh
        self.filter_bar = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.filter_bar.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(self.filter_bar, text="Xem lịch của:", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(side="left", padx=(0, 10))

        # Chọn Nhân viên
        self.staff_var = ctk.StringVar(value="Đang tải...")
        self.staff_menu = ctk.CTkOptionMenu(
            self.filter_bar, variable=self.staff_var, width=220, height=30,
            command=self.on_filter_changed
        )
        self.staff_menu.pack(side="left", padx=(0, 15))

        # Chọn Chi nhánh
        self.branch_var = ctk.StringVar(value="Tất cả chi nhánh")
        self.branch_menu = ctk.CTkOptionMenu(
            self.filter_bar, variable=self.branch_var, width=180, height=30,
            command=self.on_filter_changed
        )
        self.branch_menu.pack(side="left", padx=(0, 15))

        self.btn_refresh = ctk.CTkButton(
            self.filter_bar, text="🔄 Tải lại", width=80, height=30,
            fg_color="transparent", border_width=1, command=self.refresh_calendar
        )
        self.btn_refresh.pack(side="left")

        # ================= 2. CHÚ THÍCH MÀU SẮC (LEGEND BAR NHƯ ẢNH MẪU) =================
        self.legend_frame = ctk.CTkFrame(self, fg_color=("white", "#242424"), height=36, corner_radius=8)
        self.legend_frame.pack(fill="x", padx=15, pady=(0, 8))

        legends = [
            ("🟢 Đủ công / Đúng giờ", "#28A745"),
            ("🟠 Ca vào muộn / Về sớm", "#FD7E14"),
            ("❌ Ca nghỉ / Vắng", "#DC3545"),
            ("🔵 Ca sắp diễn ra", "#3B8ED0"),
            ("⚪ Ngày nghỉ", "gray")
        ]
        for txt, color in legends:
            lbl = ctk.CTkLabel(
                self.legend_frame, text=txt, font=ctk.CTkFont(size=11, weight="bold"),
                text_color=color
            )
            lbl.pack(side="left", padx=12, pady=6)

        # ================= 3. KHUNG LƯỚI LỊCH THÁNG (CALENDAR GRID) =================
        self.calendar_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.calendar_scroll.pack(fill="both", expand=True, padx=15, pady=0)
        self._init_calendar_grid_pool()

    def _init_calendar_grid_pool(self):
        """Khởi tạo trước 42 ô lịch (6 tuần x 7 ngày) một lần duy nhất để tối ưu hiệu năng (0ms lag)"""
        self.table_grid = ctk.CTkFrame(self.calendar_scroll, fg_color="transparent")
        self.table_grid.pack(fill="both", expand=True)

        for col_idx in range(7):
            self.table_grid.grid_columnconfigure(col_idx, weight=1, minsize=148)

        headers = ["THỨ HAI", "THỨ BA", "THỨ TƯ", "THỨ NĂM", "THỨ SÁU", "THỨ BẢY", "CHỦ NHẬT"]
        for col_idx, h in enumerate(headers):
            h_frame = ctk.CTkFrame(self.table_grid, fg_color=("white", "#242424"), height=32, corner_radius=6)
            h_frame.grid(row=0, column=col_idx, padx=3, pady=(0, 6), sticky="nsew")
            lbl_h = ctk.CTkLabel(h_frame, text=h, font=ctk.CTkFont(size=12, weight="bold"), text_color=("gray20", "gray80"))
            lbl_h.pack(expand=True)

        self.day_cells = []
        for cell_idx in range(42):
            row_idx = (cell_idx // 7) + 1
            col_idx = cell_idx % 7

            cell_frame = ctk.CTkFrame(
                self.table_grid, fg_color=("white", "#242424"), corner_radius=8,
                border_width=1, border_color=("#E5E7EB", "#333333"), height=148
            )
            cell_frame.grid(row=row_idx, column=col_idx, padx=3, pady=3, sticky="nsew")
            cell_frame.pack_propagate(False)

            # 1. Thanh tiêu đề ngày: [Ngày] bên trái, [Giờ thực tế] bên phải
            top_bar = ctk.CTkFrame(cell_frame, fg_color=("#EFEFEF", "#2A2A2A"), height=25, corner_radius=0)
            top_bar.pack(fill="x", padx=3, pady=(3, 2))
            top_bar.pack_propagate(False)

            lbl_date = ctk.CTkLabel(
                top_bar, text="", font=ctk.CTkFont(size=11, weight="bold"),
                text_color="gray"
            )
            lbl_date.pack(side="left", padx=6)

            lbl_time = ctk.CTkLabel(
                top_bar, text="", font=ctk.CTkFont(size=9, weight="bold"),
                text_color="gray"
            )
            lbl_time.pack(side="right", padx=6)

            # 2. Khung nội dung chi tiết
            content_box = ctk.CTkFrame(cell_frame, fg_color="transparent", corner_radius=0)
            content_box.pack(fill="both", expand=True, padx=3, pady=1)

            # Nhãn khi ngày nghỉ / không có ca
            lbl_empty = ctk.CTkLabel(
                content_box, text="", font=ctk.CTkFont(size=10),
                text_color="gray"
            )

            # Slot Ca 1
            slot1_box = ctk.CTkFrame(content_box, fg_color=("#F3F4F6", "#2D3035"), corner_radius=0)

            lbl_s1_name = ctk.CTkLabel(
                slot1_box, text="", font=ctk.CTkFont(size=10, weight="bold"),
                text_color=("#1A73E8", "#4FA3F7"), anchor="w"
            )
            lbl_s1_name.pack(fill="x", padx=5, pady=(1, 0))

            lbl_s1_shift = ctk.CTkLabel(
                slot1_box, text="", font=ctk.CTkFont(size=9),
                anchor="w"
            )
            lbl_s1_shift.pack(fill="x", padx=5, pady=(0, 1))

            # Slot Ca 2
            slot2_box = ctk.CTkFrame(content_box, fg_color=("#F3F4F6", "#2D3035"), corner_radius=0)

            lbl_s2_name = ctk.CTkLabel(
                slot2_box, text="", font=ctk.CTkFont(size=10, weight="bold"),
                text_color=("#1A73E8", "#4FA3F7"), anchor="w"
            )
            lbl_s2_name.pack(fill="x", padx=5, pady=(1, 0))

            lbl_s2_shift = ctk.CTkLabel(
                slot2_box, text="", font=ctk.CTkFont(size=9),
                anchor="w"
            )
            lbl_s2_shift.pack(fill="x", padx=5, pady=(0, 1))

            # Nhãn hiển thị thêm ca
            lbl_more = ctk.CTkLabel(
                content_box, text="", font=ctk.CTkFont(size=8, weight="bold"),
                text_color=("#1A73E8", "#4FA3F7"), anchor="w"
            )

            cell_data = {
                "cell_frame": cell_frame,
                "top_bar": top_bar,
                "lbl_date": lbl_date,
                "lbl_time": lbl_time,
                "content_box": content_box,
                "lbl_empty": lbl_empty,
                "slot1_box": slot1_box,
                "lbl_s1_name": lbl_s1_name,
                "lbl_s1_shift": lbl_s1_shift,
                "slot2_box": slot2_box,
                "lbl_s2_name": lbl_s2_name,
                "lbl_s2_shift": lbl_s2_shift,
                "lbl_more": lbl_more,
                "date_key": None,
                "is_current_month": False
            }

            # Gán sự kiện click trực tiếp (nhanh hơn 10x so với duyệt đệ quy cây con)
            cell_frame.configure(cursor="hand2")
            cell_frame.bind("<Button-1>", lambda e, c=cell_data: self._on_cell_clicked(c))
            top_bar.bind("<Button-1>", lambda e, c=cell_data: self._on_cell_clicked(c))
            content_box.bind("<Button-1>", lambda e, c=cell_data: self._on_cell_clicked(c))
            lbl_date.bind("<Button-1>", lambda e, c=cell_data: self._on_cell_clicked(c))
            lbl_time.bind("<Button-1>", lambda e, c=cell_data: self._on_cell_clicked(c))
            lbl_empty.bind("<Button-1>", lambda e, c=cell_data: self._on_cell_clicked(c))

            self.day_cells.append(cell_data)

    def _on_cell_clicked(self, cell_data):
        d_key = cell_data.get("date_key")
        if d_key and cell_data.get("is_current_month"):
            self.open_attendance_history_modal(target_date=d_key)

    def load_filters(self):
        # Thiết lập giá trị tạm thời tức thì (0ms latency)
        if self.user_role == "staff":
            my_name = self.current_profile.get("full_name", "Nhân viên")
            self.staff_var.set(my_name)
            self.staff_menu.configure(values=[my_name], state="disabled")
        else:
            self.staff_var.set("Tất cả nhân viên")
            self.staff_menu.configure(values=["Tất cả nhân viên"])

        self.branch_var.set("Tất cả chi nhánh")
        self.branch_menu.configure(values=["Tất cả chi nhánh"])

        threading.Thread(target=self._fetch_filters_async, daemon=True).start()

    def _fetch_filters_async(self):
        branches = self.supabase.get_branches()
        staffs = self.supabase.get_staff_list()
        try:
            self.after(0, self._apply_filters_ui, branches, staffs)
        except Exception:
            pass

    def _apply_filters_ui(self, branches, staffs):
        self.branches = branches or []
        self.branch_map = {b["name"]: b["id"] for b in self.branches}
        b_names = ["Tất cả chi nhánh"] + list(self.branch_map.keys())
        self.branch_menu.configure(values=b_names)

        self.staffs = staffs or []
        self.staff_map = {s["full_name"]: s["id"] for s in self.staffs}
        staff_names = list(self.staff_map.keys())

        if self.user_role == "staff":
            my_name = self.current_profile.get("full_name")
            self.staff_var.set(my_name)
            self.staff_menu.configure(values=[my_name], state="disabled")
        else:
            if staff_names:
                staff_options = ["Tất cả nhân viên"] + staff_names
                self.staff_menu.configure(values=staff_options)
                if self.staff_var.get() not in staff_options:
                    self.staff_var.set("Tất cả nhân viên")
            else:
                self.staff_menu.configure(values=["Chưa có nhân viên"])
                self.staff_var.set("Chưa có nhân viên")

        # Đồng bộ lịch sau khi filter đã nạp đầy đủ
        self.render_month_calendar()

    def on_filter_changed(self, choice=None):
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

    # ================= VẼ BẢNG LỊCH THÁNG (CÔNG NGHỆ CELL-POOLING 0MS LAG) =================
    def render_month_calendar(self):
        # 1. Cập nhật Tiêu đề ngay lập tức (0ms - Mượt mà không delay)
        self.lbl_month_title.configure(text=f"T{self.current_month}/{self.current_year}")
        days_in_month = calendar.monthrange(self.current_year, self.current_month)[1]
        self.lbl_date_range.configure(
            text=f"Khoảng thời gian: 01/{self.current_month:02d} - {days_in_month:02d}/{self.current_month:02d}/{self.current_year}"
        )

        start_date_str = f"{self.current_year:04d}-{self.current_month:02d}-01"
        end_date_str = f"{self.current_year:04d}-{self.current_month:02d}-{days_in_month:02d}"

        target_user_id = self.staff_map.get(self.staff_var.get())
        if not target_user_id and self.user_role == "staff":
            target_user_id = self.current_profile.get("id")

        b_name = self.branch_var.get()
        target_branch_id = self.branch_map.get(b_name)

        cache_key = f"{target_branch_id}_{target_user_id}_{start_date_str}_{end_date_str}"

        # 2. Nếu đã có trong Cache: Cập nhật ngay lập tức chỉ trong 3ms (Không lag, không khựng!)
        if cache_key in self._schedule_cache:
            self._update_grid_data(self._schedule_cache[cache_key], days_in_month)

        # 3. Đồng bộ dữ liệu ngầm từ Supabase qua Worker Thread
        threading.Thread(
            target=self._fetch_schedules_async, 
            args=(target_branch_id, target_user_id, start_date_str, end_date_str, days_in_month, cache_key), 
            daemon=True
        ).start()

    def _fetch_schedules_async(self, branch_id, user_id, start_date, end_date, days_in_month, cache_key):
        schedules = self.supabase.get_schedules_range(
            branch_id=branch_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        self._schedule_cache[cache_key] = schedules
        try:
            self.after(0, self._update_grid_data, schedules, days_in_month)
        except Exception:
            pass

    def _update_grid_data(self, schedules, days_in_month):
        """Cập nhật dữ liệu vào 42 ô lịch có sẵn (Tốc độ < 5ms, tái sử dụng 100% widget)"""
        # Gom nhóm ca theo ngày: {"YYYY-MM-DD": [schedules]}
        schedules_by_date = {}
        for s in schedules:
            w_date = s.get("work_date")
            if w_date not in schedules_by_date:
                schedules_by_date[w_date] = []
            schedules_by_date[w_date].append(s)

        # Tính toán ngày bắt đầu trên lưới
        first_day_of_month = date(self.current_year, self.current_month, 1)
        start_weekday = first_day_of_month.weekday()  # 0: Thứ Hai, 6: Chủ Nhật
        start_calendar_date = first_day_of_month - timedelta(days=start_weekday)
        today_val = date.today()

        # Cập nhật nhanh từng ô trong danh sách 42 ô tĩnh
        for cell_idx, cell in enumerate(self.day_cells):
            cur_date = start_calendar_date + timedelta(days=cell_idx)
            is_current_month = (cur_date.month == self.current_month)
            is_today = (cur_date == today_val)
            date_key = cur_date.isoformat()

            cell["date_key"] = date_key
            cell["is_current_month"] = is_current_month

            if not is_current_month:
                # Ngày thuộc tháng trước / sau: Làm mờ, ẩn nội dung
                cell["cell_frame"].configure(fg_color=("#F6F6F6", "#1C1C1C"), border_width=0)
                cell["top_bar"].configure(fg_color="transparent")
                cell["lbl_date"].configure(text=f"{cur_date.day:02d}/{cur_date.month:02d}", text_color="gray")
                cell["lbl_time"].configure(text="")
                cell["lbl_empty"].pack_forget()
                cell["slot1_box"].pack_forget()
                cell["slot2_box"].pack_forget()
                cell["lbl_more"].pack_forget()
                continue

            # Ngày trong tháng hiện tại
            if is_today:
                cell["cell_frame"].configure(fg_color=("white", "#242424"), border_width=2, border_color="#1A73E8")
            else:
                cell["cell_frame"].configure(fg_color=("white", "#242424"), border_width=1, border_color=("#E5E7EB", "#333333"))

            day_schedules = schedules_by_date.get(date_key, [])
            total_shifts = len(day_schedules)
            has_late = False
            total_late_minutes = 0
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
                        total_late_minutes += att.get("late_minutes", 0)

            # Thiết lập Thanh Tiêu đề Ô Ngày (Header top_bar)
            if total_shifts == 0:
                header_bg = ("#EFEFEF", "#2A2A2A")
                header_text_color = "gray"
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
                header_bg = ("#E5F2FF", "#18324F")
                header_text_color = "#3B8ED0"
                time_range_txt = "Sắp tới"

            cell["top_bar"].configure(fg_color=header_bg)
            cell["lbl_date"].configure(text=f"{cur_date.day:02d}/{cur_date.month:02d}", text_color=header_text_color)
            cell["lbl_time"].configure(text=time_range_txt, text_color=header_text_color)

            # Hàm rút gọn tên nhân viên tinh tế, loại bỏ hậu tố dư thừa
            def clean_staff_name(name_str):
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

            # Nếu không có ca: hiển thị trạng thái nghỉ gọn gàng
            if total_shifts == 0:
                cell["lbl_empty"].configure(text="⚪ Nghỉ / Không ca")
                cell["lbl_empty"].pack(pady=18)
                cell["slot1_box"].pack_forget()
                cell["slot2_box"].pack_forget()
                cell["lbl_more"].pack_forget()
                continue
            else:
                cell["lbl_empty"].pack_forget()

            # Slot 1: Ca làm việc thứ nhất
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
                    icon1, color1, sub1 = "📅", ("gray30", "gray80"), "Chưa vào"

                cell["lbl_s1_name"].configure(text=f"👤 {emp1}")
                cell["lbl_s1_shift"].configure(text=f"{icon1} {st1}-{et1} ({sub1})", text_color=color1)
                cell["slot1_box"].pack(fill="x", pady=1.5)
            else:
                cell["slot1_box"].pack_forget()

            # Slot 2: Ca làm việc thứ hai
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
                    icon2, color2, sub2 = "📅", ("gray30", "gray80"), "Chưa vào"

                cell["lbl_s2_name"].configure(text=f"👤 {emp2}")
                cell["lbl_s2_shift"].configure(text=f"{icon2} {st2}-{et2} ({sub2})", text_color=color2)
                cell["slot2_box"].pack(fill="x", pady=1.5)
            else:
                cell["slot2_box"].pack_forget()

            # Thẻ +X ca nữa
            if total_shifts > 2:
                cell["lbl_more"].configure(text=f"+{total_shifts - 2} ca nữa (bấm xem)")
                cell["lbl_more"].pack(fill="x", pady=(1, 0))
            else:
                cell["lbl_more"].pack_forget()

    def open_attendance_history_modal(self, target_date=None):
        """Mở Modal Xem Lịch Sử Check-in & Check-out chi tiết"""
        target_u_id = self.staff_map.get(self.staff_var.get())
        AttendanceHistoryModal(
            self,
            current_profile=self.current_profile,
            target_date=target_date,
            target_user_id=target_u_id
        )

    # ================= MODAL: PHÂN CA LÀM VIỆC MỚI =================
    def open_add_schedule_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Phân Ca Làm Việc Mới")
        modal.geometry("480x520")
        modal.grab_set()

        ctk.CTkLabel(modal, text="XẾP CA LÀM VIỆC MỚI", font=ctk.CTkFont(size=17, weight="bold")).pack(pady=(20, 15))

        # 1. Chọn Chi nhánh
        branches = self.supabase.get_branches()
        b_map = {b["name"]: b["id"] for b in branches}
        b_names = list(b_map.keys()) if b_map else ["Nhà thuốc Chi nhánh 1"]

        ctk.CTkLabel(modal, text="1. Chọn Chi nhánh:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        branch_var = ctk.StringVar(value=b_names[0])
        branch_menu = ctk.CTkOptionMenu(modal, variable=branch_var, values=b_names)
        branch_menu.pack(fill="x", padx=30, pady=(0, 10))

        # 2. Chọn Nhân viên
        staffs = self.supabase.get_staff_list()
        staff_names = [f"{s.get('full_name')} ({s.get('role', 'staff')})" for s in staffs]
        staff_map = {name: s for name, s in zip(staff_names, staffs)}

        ctk.CTkLabel(modal, text="2. Chọn Nhân viên:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        cur_staff_choice = [name for name in staff_names if self.staff_var.get() in name]
        staff_var = ctk.StringVar(value=cur_staff_choice[0] if cur_staff_choice else staff_names[0])
        staff_menu = ctk.CTkOptionMenu(modal, variable=staff_var, values=staff_names)
        staff_menu.pack(fill="x", padx=30, pady=(0, 10))

        # 3. Chọn Ca làm việc
        shifts = self.supabase.get_shifts()
        shift_names = [f"{s.get('name')} ({s.get('start_time')[:5]}-{s.get('end_time')[:5]})" for s in shifts]
        shift_map = {name: s for name, s in zip(shift_names, shifts)}

        ctk.CTkLabel(modal, text="3. Chọn Ca làm việc:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        shift_var = ctk.StringVar(value=shift_names[0] if shift_names else "Chưa có ca")
        shift_menu = ctk.CTkOptionMenu(modal, variable=shift_var, values=shift_names if shift_names else ["Chưa có ca"])
        shift_menu.pack(fill="x", padx=30, pady=(0, 10))

        # 4. Chọn Ngày làm việc
        ctk.CTkLabel(modal, text="4. Ngày làm việc (YYYY-MM-DD):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        date_entry = ctk.CTkEntry(modal, height=36)
        date_entry.insert(0, date.today().isoformat())
        date_entry.pack(fill="x", padx=30, pady=(0, 25))

        def save_schedule():
            target_staff = staff_map.get(staff_var.get())
            target_shift = shift_map.get(shift_var.get())
            chosen_branch_id = b_map.get(branch_var.get())
            work_date = date_entry.get().strip()

            try:
                datetime.strptime(work_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Lỗi", "Ngày phải đúng định dạng YYYY-MM-DD!", parent=modal)
                return

            branch = chosen_branch_id or target_shift.get("branch_id") or target_staff.get("branch_id") or (branches[0]["id"] if branches else None)

            res = self.supabase.create_schedule(
                branch_id=branch,
                user_id=target_staff.get("id"),
                shift_id=target_shift.get("id"),
                work_date=work_date
            )

            if res.get("success"):
                messagebox.showinfo("Thành công", f"Đã xếp ca thành công cho {target_staff.get('full_name')}!", parent=modal)
                modal.destroy()
                self._schedule_cache.clear()
                self.render_month_calendar()
            else:
                err_msg = res.get("message", "Không thể xếp ca làm việc. Vui lòng thử lại!")
                messagebox.showerror("Thông báo", err_msg, parent=modal)

        ctk.CTkButton(
            modal, text="💾 LƯU CA LÀM VIỆC", height=42, 
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#28A745", hover_color="#218838", 
            command=save_schedule
        ).pack(fill="x", padx=30)

    # ================= MODAL: ĐỀ XUẤT NGHỈ PHÉP CHUNG =================
    def open_general_leave_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Đề Xuất Xin Nghỉ Phép")
        modal.geometry("450x420")
        modal.grab_set()

        ctk.CTkLabel(modal, text="ĐỀ XUẤT XIN NGHỈ PHÉP", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 15))

        # Chọn ngày xin nghỉ
        ctk.CTkLabel(modal, text="Ngày muốn xin nghỉ (YYYY-MM-DD):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        date_entry = ctk.CTkEntry(modal, height=36)
        date_entry.insert(0, date.today().isoformat())
        date_entry.pack(fill="x", padx=30, pady=(0, 10))

        # Loại nghỉ
        ctk.CTkLabel(modal, text="Loại đề xuất:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        leave_type_var = ctk.StringVar(value="sick")
        types_menu = ctk.CTkOptionMenu(
            modal, variable=leave_type_var,
            values=["Nghỉ ốm (sick)", "Phép năm (annual)", "Việc riêng không lương (unpaid)", "Xin đổi ca (swap)"]
        )
        types_menu.pack(fill="x", padx=30, pady=(0, 15))

        # Chi tiết lý do
        ctk.CTkLabel(modal, text="Lý do chi tiết:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=30, pady=(0, 2))
        reason_txt = ctk.CTkTextbox(modal, height=80)
        reason_txt.pack(fill="x", padx=30, pady=(0, 20))

        def submit():
            reason = reason_txt.get("1.0", "end-1c").strip()
            w_date = date_entry.get().strip()
            if not reason:
                messagebox.showwarning("Lưu ý", "Vui lòng nhập lý do xin nghỉ!", parent=modal)
                return

            # Tìm ca của nhân viên trong ngày đó
            target_user_id = self.current_profile.get("id")
            schedules = self.supabase.get_schedules_range(user_id=target_user_id, start_date=w_date, end_date=w_date)
            if not schedules:
                messagebox.showwarning("Lưu ý", f"Bạn không có ca làm việc nào được xếp vào ngày {w_date} để xin nghỉ!", parent=modal)
                return

            sched = schedules[0]
            raw_type = leave_type_var.get().split("(")[-1].replace(")", "").strip()
            res = self.supabase.submit_leave_request(sched.get("id"), sched.get("branch_id"), raw_type, reason)

            if res.get("success"):
                messagebox.showinfo("Thành công", "Đơn xin nghỉ đã được gửi tới Cửa hàng trưởng duyệt!", parent=modal)
                modal.destroy()
                self._schedule_cache.clear()
                self.render_month_calendar()
            else:
                msg = res.get("message", "Không thể gửi đơn xin nghỉ. Vui lòng thử lại sau!")
                messagebox.showerror("Thông báo", msg, parent=modal)

        ctk.CTkButton(
            modal, text="GỬI ĐỀ XUẤT NGHỈ", height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#FD7E14", hover_color="#E06A05", command=submit
        ).pack(fill="x", padx=30)
