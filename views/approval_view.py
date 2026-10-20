import threading
import webbrowser
import customtkinter as ctk
from tkinter import messagebox
from core.supabase_service import SupabaseService

class ApprovalView(ctk.CTkFrame):
    def __init__(self, master, current_profile):
        super().__init__(master, fg_color="transparent")
        self.current_profile = current_profile
        self.supabase = SupabaseService()
        self.branch_id = self.current_profile.get("branch_id")
        self.user_role = self.current_profile.get("role", "storemanager")

        self.setup_ui()

    def setup_ui(self):
        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color=("white", "#242424"), height=60, corner_radius=12)
        self.header_frame.pack(fill="x", padx=20, pady=(20, 15))

        self.title_lbl = ctk.CTkLabel(
            self.header_frame, text="📋 TRUNG TÂM PHÊ DUYỆT YÊU CẦU",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.title_lbl.pack(side="left", padx=20, pady=15)

        self.btn_refresh = ctk.CTkButton(
            self.header_frame, text="🔄 Làm mới", width=90, height=34,
            command=self.refresh_current_tab
        )
        self.btn_refresh.pack(side="right", padx=20, pady=13)

        # TabView: Tab 1 (Đơn xin nghỉ), Tab 2 (Giải trình & Ảnh)
        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=0)

        self.tab_leave = self.tabview.add("Đơn xin nghỉ phép")
        self.tab_proof = self.tabview.add("Giải trình quên chấm công (Kèm ảnh)")

        # Setup Tab 1
        self.scroll_leave = ctk.CTkScrollableFrame(self.tab_leave, fg_color="transparent")
        self.scroll_leave.pack(fill="both", expand=True, padx=10, pady=10)

        # Setup Tab 2
        self.scroll_proof = ctk.CTkScrollableFrame(self.tab_proof, fg_color="transparent")
        self.scroll_proof.pack(fill="both", expand=True, padx=10, pady=10)

        # Async load cả 2 tabs (0ms UI latency)
        self.load_leave_requests()
        self.load_attendance_proofs()

    def refresh_current_tab(self):
        self.load_leave_requests()
        self.load_attendance_proofs()

    # ================= TAB 1: DUYỆT ĐƠN NGHỈ =================
    def load_leave_requests(self):
        for widget in self.scroll_leave.winfo_children():
            widget.destroy()

        loading_lbl = ctk.CTkLabel(self.scroll_leave, text="⏳ Đang tải danh sách đơn xin nghỉ...", text_color="gray")
        loading_lbl.pack(pady=40)

        b_id = self.branch_id if self.user_role != "admin" else None
        threading.Thread(target=self._fetch_leave_requests_async, args=(b_id,), daemon=True).start()

    def _fetch_leave_requests_async(self, b_id):
        requests = self.supabase.get_leave_requests(branch_id=b_id)
        try:
            self.after(0, self._render_leave_requests, requests)
        except Exception:
            pass

    def _render_leave_requests(self, requests):
        for widget in self.scroll_leave.winfo_children():
            widget.destroy()

        if not requests:
            lbl = ctk.CTkLabel(self.scroll_leave, text="Không có đơn xin nghỉ nào cần duyệt.", text_color="gray")
            lbl.pack(pady=40)
            return

        for req in requests:
            card = ctk.CTkFrame(self.scroll_leave, fg_color=("white", "#242424"), corner_radius=10)
            card.pack(fill="x", pady=6, padx=5)

            staff_name = req.get("profiles", {}).get("full_name", "Nhân viên")
            branch_name = req.get("branches", {}).get("name", "")
            leave_type = req.get("leave_type", "")
            reason = req.get("reason", "")
            status = req.get("status", "pending")
            schedule = req.get("schedules", {})
            work_date = schedule.get("work_date", "")
            shift_info = schedule.get("shifts", {})
            shift_name = shift_info.get("name", "Ca làm")

            type_map = {
                "sick": "Nghỉ ốm",
                "annual": "Phép năm",
                "unpaid": "Việc riêng không lương",
                "swap": "Xin đổi ca"
            }
            type_str = type_map.get(leave_type, leave_type)

            # Header card
            header_txt = f"👤 {staff_name}  •  🏥 {branch_name}  •  Loại: {type_str}"
            lbl_title = ctk.CTkLabel(card, text=header_txt, font=ctk.CTkFont(size=14, weight="bold"))
            lbl_title.pack(anchor="w", padx=15, pady=(12, 4))

            # Thông tin ca & lý do
            info_txt = f"📅 Ngày nghỉ: {work_date} ({shift_name})\n💬 Lý do: {reason}"
            lbl_info = ctk.CTkLabel(card, text=info_txt, font=ctk.CTkFont(size=12), justify="left")
            lbl_info.pack(anchor="w", padx=15, pady=(0, 10))

            # Nút duyệt / từ chối
            action_frame = ctk.CTkFrame(card, fg_color="transparent")
            action_frame.pack(fill="x", padx=15, pady=(0, 12))

            if status == "pending":
                btn_approve = ctk.CTkButton(
                    action_frame, text="✅ Phê duyệt", width=100, height=32,
                    fg_color="#28A745", hover_color="#218838",
                    command=lambda r=req, b_app=None, b_rej=None: self.handle_review_leave(r, "approved")
                )
                btn_approve.pack(side="right", padx=(5, 0))

                btn_reject = ctk.CTkButton(
                    action_frame, text="❌ Từ chối", width=90, height=32,
                    fg_color="#DC3545", hover_color="#C82333",
                    command=lambda r=req: self.handle_review_leave(r, "rejected")
                )
                btn_reject.pack(side="right", padx=(0, 5))
            else:
                st_color = "#28A745" if status == "approved" else "#DC3545"
                st_txt = "ĐÃ DUYỆT" if status == "approved" else "ĐÃ TỪ CHỐI"
                lbl_st = ctk.CTkLabel(action_frame, text=st_txt, text_color=st_color, font=ctk.CTkFont(size=12, weight="bold"))
                lbl_st.pack(side="right")

    def handle_review_leave(self, request_item, status):
        reviewer_id = self.current_profile.get("id")
        req_id = request_item.get("id")

        def run_review():
            res = self.supabase.review_leave_request(req_id, status, reviewer_id)
            try:
                self.after(0, self._on_leave_review_done, res, status)
            except Exception:
                pass

        threading.Thread(target=run_review, daemon=True).start()

    def _on_leave_review_done(self, res, status):
        if res.get("success"):
            action_name = "phê duyệt" if status == "approved" else "từ chối"
            messagebox.showinfo("Thành công", f"Đã {action_name} đơn xin nghỉ!")
            self.load_leave_requests()
        else:
            msg = res.get("message", "Không thể cập nhật trạng thái đơn.")
            messagebox.showerror("Thông báo", msg)

    # ================= TAB 2: DUYỆT MINH CHỨNG & ẢNH =================
    def load_attendance_proofs(self):
        for widget in self.scroll_proof.winfo_children():
            widget.destroy()

        loading_lbl = ctk.CTkLabel(self.scroll_proof, text="⏳ Đang tải danh sách minh chứng...", text_color="gray")
        loading_lbl.pack(pady=40)

        b_id = self.branch_id if self.user_role != "admin" else None
        threading.Thread(target=self._fetch_attendance_proofs_async, args=(b_id,), daemon=True).start()

    def _fetch_attendance_proofs_async(self, b_id):
        proofs = self.supabase.get_attendance_proofs(branch_id=b_id)
        try:
            self.after(0, self._render_attendance_proofs, proofs)
        except Exception:
            pass

    def _render_attendance_proofs(self, proofs):
        for widget in self.scroll_proof.winfo_children():
            widget.destroy()

        if not proofs:
            lbl = ctk.CTkLabel(self.scroll_proof, text="Không có giải trình quên chấm công nào cần duyệt.", text_color="gray")
            lbl.pack(pady=40)
            return

        for p in proofs:
            card = ctk.CTkFrame(self.scroll_proof, fg_color=("white", "#242424"), corner_radius=10)
            card.pack(fill="x", pady=6, padx=5)

            staff_name = p.get("profiles", {}).get("full_name", "Nhân viên")
            branch_name = p.get("branches", {}).get("name", "")
            image_url = p.get("image_url", "")
            note = p.get("note", "Không có ghi chú")
            created_at = p.get("created_at", "")[:19].replace("T", " ")
            status = p.get("status", "pending")

            header_txt = f"👤 {staff_name}  •  🏥 {branch_name}  •  Thời gian gửi: {created_at}"
            lbl_title = ctk.CTkLabel(card, text=header_txt, font=ctk.CTkFont(size=14, weight="bold"))
            lbl_title.pack(anchor="w", padx=15, pady=(12, 4))

            lbl_note = ctk.CTkLabel(card, text=f"💬 Giải trình: {note}", font=ctk.CTkFont(size=12))
            lbl_note.pack(anchor="w", padx=15, pady=(0, 10))

            action_frame = ctk.CTkFrame(card, fg_color="transparent")
            action_frame.pack(fill="x", padx=15, pady=(0, 12))

            # Nút mở xem ảnh
            btn_view_img = ctk.CTkButton(
                action_frame, text="🖼️ Xem ảnh bằng chứng", width=140, height=32,
                fg_color="#3B8ED0", command=lambda url=image_url: webbrowser.open(url)
            )
            btn_view_img.pack(side="left")

            if status == "pending":
                btn_approve = ctk.CTkButton(
                    action_frame, text="✅ Duyệt công", width=100, height=32,
                    fg_color="#28A745", hover_color="#218838",
                    command=lambda pr=p: self.handle_review_proof(pr, "approved")
                )
                btn_approve.pack(side="right", padx=(5, 0))

                btn_reject = ctk.CTkButton(
                    action_frame, text="❌ Từ chối", width=90, height=32,
                    fg_color="#DC3545", hover_color="#C82333",
                    command=lambda pr=p: self.handle_review_proof(pr, "rejected")
                )
                btn_reject.pack(side="right", padx=(0, 5))
            else:
                st_color = "#28A745" if status == "approved" else "#DC3545"
                st_txt = "ĐÃ DUYỆT" if status == "approved" else "ĐÃ TỪ CHỐI"
                lbl_st = ctk.CTkLabel(action_frame, text=st_txt, text_color=st_color, font=ctk.CTkFont(size=12, weight="bold"))
                lbl_st.pack(side="right")

    def handle_review_proof(self, proof_item, status):
        reviewer_id = self.current_profile.get("id")
        proof_id = proof_item.get("id")

        def run_review():
            res = self.supabase.review_attendance_proof(proof_id, status, reviewer_id)
            try:
                self.after(0, self._on_proof_review_done, res, status)
            except Exception:
                pass

        threading.Thread(target=run_review, daemon=True).start()

    def _on_proof_review_done(self, res, status):
        if res.get("success"):
            action_name = "duyệt" if status == "approved" else "từ chối"
            messagebox.showinfo("Thành công", f"Đã {action_name} minh chứng!")
            self.load_attendance_proofs()
        else:
            msg = res.get("message", "Không thể cập nhật trạng thái minh chứng.")
            messagebox.showerror("Thông báo", msg)
