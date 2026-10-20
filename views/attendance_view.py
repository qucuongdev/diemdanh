import time
import threading
from datetime import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.hardware import get_hardware_uuid
from core.supabase_service import SupabaseService

class AttendanceView(ctk.CTkFrame):
    def __init__(self, master, current_profile, on_logout):
        super().__init__(master, fg_color="transparent")
        self.current_profile = current_profile
        self.on_logout = on_logout
        self.supabase = SupabaseService()
        self.device_uuid = get_hardware_uuid()

        self.today_schedule = None
        self.today_attendance = None
        self.clock_running = True
        self.clock_timer_id = None

        self.setup_ui()
        self.load_schedule()
        self.update_clock()

    def destroy(self):
        self.clock_running = False
        if self.clock_timer_id:
            try:
                self.after_cancel(self.clock_timer_id)
            except Exception:
                pass
        super().destroy()

    def setup_ui(self):
        # Header: Thông tin nhân viên & Nút Đăng xuất nhanh
        self.header_frame = ctk.CTkFrame(self, fg_color=("white", "#242424"), height=70, corner_radius=12)
        self.header_frame.pack(fill="x", padx=20, pady=(20, 15))

        # Tên nhân viên và Chi nhánh
        user_name = self.current_profile.get("full_name", "Dược sĩ")
        role = self.current_profile.get("role", "staff").upper()
        branch_info = self.current_profile.get("branches")
        branch_name = branch_info.get("name") if branch_info else "Tổng bộ / Quản trị"

        self.user_label = ctk.CTkLabel(
            self.header_frame, 
            text=f"👤 {user_name}  •  {role}", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.user_label.pack(side="left", padx=(20, 10), pady=15)

        self.branch_badge = ctk.CTkLabel(
            self.header_frame, 
            text=f"🏥 {branch_name}", 
            font=ctk.CTkFont(size=12),
            text_color="#3B8ED0"
        )
        self.branch_badge.pack(side="left", pady=15)

        # NÚT ĐĂNG XUẤT NHANH (GIAO CA)
        self.logout_btn = ctk.CTkButton(
            self.header_frame, 
            text="🚪 ĐĂNG XUẤT (GIAO CA)", 
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#D9534F",
            hover_color="#C9302C",
            height=38,
            command=self.handle_logout
        )
        self.logout_btn.pack(side="right", padx=(10, 20), pady=15)

        # NÚT XEM LỊCH SỬ CHECK-IN / CHECK-OUT
        self.history_btn = ctk.CTkButton(
            self.header_frame,
            text="📜 LỊCH SỬ CHẤM CÔNG",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#17A2B8",
            hover_color="#138496",
            height=38,
            command=self.open_attendance_history_modal
        )
        self.history_btn.pack(side="right", padx=(10, 0), pady=15)

        # Content chia làm 2 cột: Cột trái (Đồng hồ & Nút Chấm công), Cột phải (Chi tiết ca & Minh chứng)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=0)
        self.content_frame.grid_columnconfigure(0, weight=3)
        self.content_frame.grid_columnconfigure(1, weight=2)

        # ========== CỘT TRÁI: ĐỒNG HỒ & CHẤM CÔNG ==========
        self.left_col = ctk.CTkFrame(self.content_frame, fg_color=("white", "#242424"), corner_radius=16)
        self.left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)

        # Đồng hồ số thời gian thực
        self.clock_label = ctk.CTkLabel(
            self.left_col, 
            text="00:00:00", 
            font=ctk.CTkFont(family="Consolas", size=54, weight="bold"),
            text_color="#2CC985"
        )
        self.clock_label.pack(pady=(35, 0))

        self.date_label = ctk.CTkLabel(
            self.left_col, 
            text="", 
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.date_label.pack(pady=(0, 25))

        # Bảng thông báo trạng thái Zero Tolerance (Cảnh báo trễ/đúng giờ)
        self.status_box = ctk.CTkFrame(self.left_col, fg_color=("#F0F0F0", "#1A1A1A"), corner_radius=10)
        self.status_box.pack(fill="x", padx=30, pady=(0, 25))

        self.status_text = ctk.CTkLabel(
            self.status_box, 
            text="Đang kiểm tra lịch làm việc hôm nay...", 
            font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=380
        )
        self.status_text.pack(padx=20, pady=15)

        # 2 Nút Chấm Công Lớn
        self.action_box = ctk.CTkFrame(self.left_col, fg_color="transparent")
        self.action_box.pack(fill="x", padx=30, pady=(0, 30))
        self.action_box.grid_columnconfigure(0, weight=1)
        self.action_box.grid_columnconfigure(1, weight=1)

        self.btn_check_in = ctk.CTkButton(
            self.action_box, 
            text="✅ CHECK-IN\n(VÀO CA)", 
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#28A745",
            hover_color="#218838",
            height=65,
            corner_radius=12,
            command=self.handle_check_in
        )
        self.btn_check_in.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.btn_check_out = ctk.CTkButton(
            self.action_box, 
            text="🏁 CHECK-OUT\n(TAN CA)", 
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#FD7E14",
            hover_color="#E06A05",
            height=65,
            corner_radius=12,
            command=self.handle_check_out
        )
        self.btn_check_out.grid(row=0, column=1, padx=(8, 0), sticky="ew")

        # ========== CỘT PHẢI: CHI TIẾT CA & GIẢI TRÌNH ==========
        self.right_col = ctk.CTkFrame(self.content_frame, fg_color=("white", "#242424"), corner_radius=16)
        self.right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)

        self.info_title = ctk.CTkLabel(
            self.right_col, 
            text="THÔNG TIN CA HÔM NAY", 
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.info_title.pack(anchor="w", padx=25, pady=(25, 15))

        self.shift_detail_label = ctk.CTkLabel(
            self.right_col, 
            text="Chưa có dữ liệu", 
            font=ctk.CTkFont(size=13),
            justify="left",
            anchor="w"
        )
        self.shift_detail_label.pack(fill="x", padx=25, pady=(0, 20))

        # Khu vực giải trình quên chấm công (kèm ảnh nén Pillow)
        self.proof_box = ctk.CTkFrame(self.right_col, fg_color=("#F0F0F0", "#1A1A1A"), corner_radius=12)
        self.proof_box.pack(fill="x", padx=25, pady=(0, 20))

        self.proof_title = ctk.CTkLabel(
            self.proof_box, 
            text="Quên Check-out? Gửi giải trình", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.proof_title.pack(anchor="w", padx=15, pady=(15, 5))

        self.proof_desc = ctk.CTkLabel(
            self.proof_box, 
            text="Tải ảnh bằng chứng tại quầy để Quản lý duyệt lại công cho bạn.", 
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=250,
            justify="left"
        )
        self.proof_desc.pack(anchor="w", padx=15, pady=(0, 10))

        self.btn_upload_proof = ctk.CTkButton(
            self.proof_box, 
            text="📷 Tải ảnh bằng chứng", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3B8ED0",
            height=34,
            command=self.handle_upload_proof
        )
        self.btn_upload_proof.pack(fill="x", padx=15, pady=(0, 15))

    def update_clock(self):
        if not self.clock_running:
            return
        # Nếu tab đang ẩn (pack_forget), không redraw canvas để tiết kiệm CPU & RAM
        if not self.winfo_ismapped():
            self.clock_timer_id = self.after(1000, self.update_clock)
            return

        now = datetime.now()
        self.clock_label.configure(text=now.strftime("%H:%M:%S"))
        # Thứ trong tuần tiếng Việt
        days = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        day_vn = days[now.weekday()]
        self.date_label.configure(text=f"{day_vn}, ngày {now.strftime('%d/%m/%Y')}")

        # Tự động mở nút Check-out khi đồng hồ điểm đúng giờ tan ca
        if self.today_schedule and self.today_attendance and not self.today_attendance.get("check_out"):
            shift = self.today_schedule.get("shifts") or {}
            end_time = shift.get("end_time", "16:00:00")
            try:
                end_h, end_m = map(int, end_time[:5].split(":"))
                shift_end_t = datetime.strptime(f"{end_h}:{end_m}", "%H:%M").time()
                if now.time() >= shift_end_t:
                    if str(self.btn_check_out.cget("state")) != "normal":
                        self.btn_check_out.configure(state="normal", text="🏁 CHECK-OUT\n(TAN CA)")
                        self.status_text.configure(
                            text=f"🔔 Đã hết ca ({end_time[:5]})! Vui lòng bấm Check-out hoàn thành ca.",
                            text_color="#28A745"
                        )
                else:
                    if str(self.btn_check_out.cget("state")) != "disabled":
                        self.btn_check_out.configure(state="disabled", text=f"🏁 CHECK-OUT\n(HẾT CA LÚC {end_time[:5]})")
            except Exception:
                pass

        self.clock_timer_id = self.after(1000, self.update_clock)

    def load_schedule(self):
        """Đọc lịch làm việc và trạng thái chấm công của ngày hôm nay (Async không lag)"""
        user_id = self.current_profile.get("id")
        threading.Thread(target=self._fetch_schedule_async, args=(user_id,), daemon=True).start()

    def _fetch_schedule_async(self, user_id):
        res = self.supabase.get_today_schedule(user_id)
        try:
            self.after(0, self._apply_schedule_ui, res)
        except Exception:
            pass

    def _apply_schedule_ui(self, res):
        if not res.get("success") or not res.get("schedules"):
            self.status_text.configure(
                text="Hôm nay bạn không có lịch phân ca làm việc tại quầy!",
                text_color="gray"
            )
            self.shift_detail_label.configure(text="• Không có ca được xếp hôm nay.")
            self.btn_check_in.configure(state="disabled")
            self.btn_check_out.configure(state="disabled")
            return

        self.today_schedule = res["schedules"][0]
        shift = self.today_schedule.get("shifts", {})
        shift_name = shift.get("name", "Ca chưa đặt tên")
        start_time = shift.get("start_time", "08:00:00")
        end_time = shift.get("end_time", "16:00:00")

        # Xử lý attendance an toàn (hỗ trợ cả dạng dict và list từ Supabase)
        raw_att = self.today_schedule.get("attendance")
        if isinstance(raw_att, list):
            self.today_attendance = raw_att[0] if raw_att else None
        elif isinstance(raw_att, dict):
            self.today_attendance = raw_att
        else:
            self.today_attendance = None

        detail_text = (
            f"• Ca: {shift_name}\n"
            f"• Thời gian: {start_time[:5]} - {end_time[:5]}\n"
            f"• Trạng thái lịch: {self.today_schedule.get('status', 'scheduled').upper()}"
        )
        self.shift_detail_label.configure(text=detail_text)

        # Cập nhật trạng thái các nút
        if not self.today_attendance:
            # Chưa Check-in -> Mở nút Check-in, Khóa nút Check-out
            self.btn_check_in.configure(state="normal", text="✅ CHECK-IN\n(VÀO CA)")
            self.btn_check_out.configure(state="disabled", text="🏁 CHECK-OUT\n(CHƯA VÀO CA)")
            self.status_text.configure(
                text="Bạn chưa Check-in vào ca. Vui lòng bấm Check-in!",
                text_color="#3B8ED0"
            )
        else:
            # ĐÃ CHECK-IN -> KHÓA NÚT CHECK-IN NGAY LẬP TỨC (DISABLED)
            self.btn_check_in.configure(state="disabled", text="✅ ĐÃ CHECK-IN\n(ĐANG TRONG CA)")
            check_in_time = self.today_attendance.get("check_in", "")
            is_late = self.today_attendance.get("is_late", False)
            late_min = self.today_attendance.get("late_minutes", 0)
            time_display = check_in_time[11:19] if len(check_in_time) >= 19 else check_in_time

            if not self.today_attendance.get("check_out"):
                # Đang trong ca làm việc: Kiểm tra đã đến giờ tan ca chưa
                now_t = datetime.now().time()
                is_shift_ended = False
                try:
                    end_h, end_m = map(int, end_time[:5].split(":"))
                    shift_end_t = datetime.strptime(f"{end_h}:{end_m}", "%H:%M").time()
                    is_shift_ended = (now_t >= shift_end_t)
                except Exception:
                    is_shift_ended = True

                if is_shift_ended:
                    # ĐÃ HẾT CA -> Cho phép bấm Check-out
                    self.btn_check_out.configure(state="normal", text="🏁 CHECK-OUT\n(TAN CA)")
                    if is_late:
                        self.status_text.configure(
                            text=f"⚠️ Vào ca: {time_display} (Trễ {late_min}p). Đã hết ca ({end_time[:5]}), hãy bấm Check-out!",
                            text_color="#FD7E14"
                        )
                    else:
                        self.status_text.configure(
                            text=f"🔔 Đã hết ca làm việc ({end_time[:5]})! Vui lòng bấm Check-out hoàn thành ca.",
                            text_color="#28A745"
                        )
                else:
                    # CHƯA HẾT CA -> BẮT BUỘC KHÓA NÚT CHECK-OUT (DISABLED)
                    self.btn_check_out.configure(state="disabled", text=f"🏁 CHECK-OUT\n(HẾT CA LÚC {end_time[:5]})")
                    if is_late:
                        self.status_text.configure(
                            text=f"⚠️ Đã Check-in: {time_display} (ĐI TRỄ {late_min} PHÚT)\n(Đang trong ca làm việc. Ca kết thúc lúc {end_time[:5]})",
                            text_color="#FD7E14"
                        )
                    else:
                        self.status_text.configure(
                            text=f"✅ Đã Check-in đúng giờ: {time_display}\n(Đang trong ca làm việc. Ca kết thúc lúc {end_time[:5]})",
                            text_color="#28A745"
                        )
            else:
                # Đã hoàn thành cả Check-in và Check-out -> Khóa cả 2 nút
                self.btn_check_in.configure(state="disabled", text="✅ ĐÃ HOÀN THÀNH")
                self.btn_check_out.configure(state="disabled", text="🏁 ĐÃ CHECK-OUT")
                check_out_time = self.today_attendance.get("check_out", "")
                out_display = check_out_time[11:19] if len(check_out_time) >= 19 else check_out_time
                self.status_text.configure(
                    text=f"🎉 Bạn đã hoàn thành ca làm việc hôm nay!\n(Vào ca: {time_display}  •  Tan ca: {out_display})",
                    text_color="#28A745"
                )

    def handle_check_in(self):
        if not self.today_schedule:
            messagebox.showwarning("Cảnh báo", "Bạn không có ca làm việc hôm nay để Check-in!")
            return

        self.btn_check_in.configure(state="disabled", text="ĐANG XỬ LÝ...")
        schedule_id = self.today_schedule.get("id")

        def check_in_worker():
            res = self.supabase.check_in(schedule_id, self.device_uuid)
            try:
                self.after(0, self._on_check_in_done, res)
            except Exception:
                pass

        threading.Thread(target=check_in_worker, daemon=True).start()

    def _on_check_in_done(self, res):
        if isinstance(res, dict) and res.get("success"):
            # Lập tức khóa nút Check-in ngay trên giao diện
            self.btn_check_in.configure(state="disabled", text="✅ ĐÃ CHECK-IN\n(ĐANG TRONG CA)")
            msg = res.get("message", "Check-in thành công!")
            messagebox.showinfo("Thông báo Chấm công", msg)
        else:
            self.btn_check_in.configure(state="normal", text="✅ CHECK-IN\n(VÀO CA)")
            err = res.get("message") if isinstance(res, dict) else "Không thể ghi nhận giờ vào ca. Vui lòng kiểm tra lại thiết bị hoặc kết nối!"
            messagebox.showerror("Thông báo", err)

        self.load_schedule()

    def handle_check_out(self):
        if not self.today_schedule or not self.today_attendance:
            messagebox.showwarning("Cảnh báo", "Bạn chưa Check-in nên không thể Check-out!")
            return

        # RÀNG BUỘC NGHIÊM NGẶT: CHỈ ĐƯỢC CHECK-OUT KHI ĐÃ ĐẾN HOẶC QUA GIỜ TAN CA
        shift = self.today_schedule.get("shifts") or {}
        end_time = shift.get("end_time", "16:00:00")
        try:
            end_h, end_m = map(int, end_time[:5].split(":"))
            shift_end_t = datetime.strptime(f"{end_h}:{end_m}", "%H:%M").time()
            if datetime.now().time() < shift_end_t:
                messagebox.showwarning(
                    "Chưa đến giờ tan ca", 
                    f"Ca làm việc của bạn kết thúc lúc {end_time[:5]}.\nHiện tại chưa hết ca nên bạn chưa được phép Check-out!"
                )
                return
        except Exception:
            pass

        self.btn_check_out.configure(state="disabled", text="ĐANG XỬ LÝ...")
        attendance_id = self.today_attendance.get("id")

        def check_out_worker():
            res = self.supabase.check_out(attendance_id, self.device_uuid)
            try:
                self.after(0, self._on_check_out_done, res)
            except Exception:
                pass

        threading.Thread(target=check_out_worker, daemon=True).start()

    def _on_check_out_done(self, res):
        if isinstance(res, dict) and res.get("success"):
            self.btn_check_out.configure(state="disabled", text="🏁 ĐÃ CHECK-OUT")
            msg = res.get("message", "Check-out hoàn thành!")
            messagebox.showinfo("Thông báo Chấm công", msg)
        else:
            self.btn_check_out.configure(state="normal", text="🏁 CHECK-OUT\n(TAN CA)")
            err = res.get("message") if isinstance(res, dict) else "Không thể ghi nhận giờ tan ca. Vui lòng thử lại!"
            messagebox.showerror("Thông báo", err)

        self.load_schedule()

    def handle_upload_proof(self):
        file_path = filedialog.askopenfilename(
            title="Chọn ảnh minh chứng",
            filetypes=[("Image files", "*.jpg;*.jpeg;*.png;*.webp")]
        )
        if not file_path:
            return

        user_id = self.current_profile.get("id")
        self.btn_upload_proof.configure(state="disabled", text="Đang nén & tải ảnh...")

        def upload_worker():
            res = self.supabase.upload_compressed_proof(file_path, user_id)
            try:
                self.after(0, self._on_upload_proof_done, res)
            except Exception:
                pass

        threading.Thread(target=upload_worker, daemon=True).start()

    def _on_upload_proof_done(self, res):
        self.btn_upload_proof.configure(state="normal", text="📷 Tải ảnh bằng chứng")
        if res.get("success"):
            messagebox.showinfo("Thành công", "Đã nén và gửi ảnh minh chứng lên hệ thống để Quản lý duyệt!")
        else:
            msg = res.get("message", "Không thể gửi ảnh minh chứng. Vui lòng thử lại!")
            messagebox.showerror("Thông báo", msg)

    def handle_logout(self):
        self.clock_running = False
        self.supabase.logout()
        self.on_logout()

    def open_attendance_history_modal(self):
        from views.attendance_history_modal import AttendanceHistoryModal
        AttendanceHistoryModal(
            self,
            current_profile=self.current_profile,
            target_user_id=self.current_profile.get("id")
        )
