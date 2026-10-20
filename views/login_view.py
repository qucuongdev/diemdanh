import threading
import customtkinter as ctk
from core.hardware import get_hardware_uuid
from core.supabase_service import SupabaseService

class LoginView(ctk.CTkFrame):
    def __init__(self, master, on_login_success):
        super().__init__(master, fg_color="transparent")
        self.on_login_success = on_login_success
        self.supabase = SupabaseService()
        self.device_uuid = get_hardware_uuid()

        self.setup_ui()

    def setup_ui(self):
        # Card chứa form đăng nhập
        self.card = ctk.CTkFrame(self, width=420, corner_radius=16, fg_color=("white", "#242424"))
        self.card.place(relx=0.5, rely=0.5, anchor="center")

        # Tiêu đề
        self.title_label = ctk.CTkLabel(
            self.card, 
            text="NHÀ THUỐC ĐIỂM DANH", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title_label.pack(pady=(30, 5), padx=30)

        self.sub_label = ctk.CTkLabel(
            self.card, 
            text="Hệ thống chấm công quầy chuỗi nhà thuốc", 
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.sub_label.pack(pady=(0, 20), padx=30)

        # Khung bảo mật phần cứng (đã mã hóa che giấu UUID, chống sao chép và giả mạo)
        self.device_box = ctk.CTkFrame(self.card, fg_color=("#F0F0F0", "#1A1A1A"), corner_radius=8)
        self.device_box.pack(fill="x", padx=30, pady=(0, 20))

        self.device_title = ctk.CTkLabel(
            self.device_box, 
            text="🔒 XÁC THỰC PHẦN CỨNG MÁY QUẦY", 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#28A745"
        )
        self.device_title.pack(anchor="w", padx=10, pady=(6, 2))

        masked_uuid = f"••••-••••-••••-{self.device_uuid[-6:]}" if len(self.device_uuid) > 6 else "••••••••"
        self.device_val = ctk.CTkLabel(
            self.device_box, 
            text=f"Trạng thái: Đã khóa theo máy quầy ({masked_uuid})", 
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="gray"
        )
        self.device_val.pack(anchor="w", padx=10, pady=(0, 6))

        # Input Email
        self.email_label = ctk.CTkLabel(self.card, text="Tài khoản Email:", font=ctk.CTkFont(size=12, weight="bold"))
        self.email_label.pack(anchor="w", padx=30, pady=(5, 2))

        self.email_entry = ctk.CTkEntry(self.card, placeholder_text="duocsi@nhathuoc.com", height=38, corner_radius=8)
        self.email_entry.pack(fill="x", padx=30, pady=(0, 10))

        # Input Password
        self.pass_label = ctk.CTkLabel(self.card, text="Mật khẩu:", font=ctk.CTkFont(size=12, weight="bold"))
        self.pass_label.pack(anchor="w", padx=30, pady=(5, 2))

        self.pass_entry = ctk.CTkEntry(self.card, placeholder_text="••••••••", show="•", height=38, corner_radius=8)
        self.pass_entry.pack(fill="x", padx=30, pady=(0, 15))
        self.pass_entry.bind("<Return>", lambda event: self.handle_login())

        # Error label
        self.error_label = ctk.CTkLabel(self.card, text="", font=ctk.CTkFont(size=12), text_color="#FF4C4C", wraplength=340)
        self.error_label.pack(padx=30, pady=(0, 10))

        # Nút Đăng nhập
        self.login_btn = ctk.CTkButton(
            self.card, 
            text="ĐĂNG NHẬP VÀO CA", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            corner_radius=8,
            command=self.handle_login
        )
        self.login_btn.pack(fill="x", padx=30, pady=(0, 30))

    def handle_login(self):
        email = self.email_entry.get().strip()
        password = self.pass_entry.get()

        if not email or not password:
            self.error_label.configure(text="Vui lòng nhập đầy đủ Email và Mật khẩu!")
            return

        # Hỗ trợ gõ nhanh tài khoản không cần gõ @domain (VD: gõ 'admin' -> 'admin@nhathuoc.com')
        if "@" not in email:
            email = f"{email}@nhathuoc.com"

        self.error_label.configure(text="Đang xác thực tài khoản...", text_color="gray")
        self.login_btn.configure(state="disabled", text="ĐANG XỬ LÝ...")

        def login_worker():
            res = self.supabase.login(email, password)
            if not res["success"]:
                try:
                    self.after(0, self._on_login_failed, res["message"])
                except Exception:
                    pass
                return

            profile = res["profile"]
            user_role = profile.get("role")
            branch_id = profile.get("branch_id")

            # Kiểm tra thiết bị nếu là Staff hoặc Manager (Admin được miễn trừ kiểm tra máy)
            if user_role in ("staff", "storemanager") and branch_id:
                is_allowed = self.supabase.check_device_permission(branch_id, self.device_uuid)
                if not is_allowed:
                    self.supabase.logout()
                    err_msg = "Máy tính này chưa được đăng ký làm việc tại Chi nhánh của bạn! Vui lòng liên hệ Admin."
                    try:
                        self.after(0, self._on_login_failed, err_msg)
                    except Exception:
                        pass
                    return

            try:
                self.after(0, self._on_login_succeeded, profile)
            except Exception:
                pass

        threading.Thread(target=login_worker, daemon=True).start()

    def _on_login_failed(self, msg):
        self.error_label.configure(text=msg, text_color="#FF4C4C")
        self.login_btn.configure(state="normal", text="ĐĂNG NHẬP VÀO CA")

    def _on_login_succeeded(self, profile):
        self.login_btn.configure(state="normal", text="ĐĂNG NHẬP VÀO CA")
        self.error_label.configure(text="")
        self.on_login_success(profile)
