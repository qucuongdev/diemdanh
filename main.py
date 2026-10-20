import sys
import customtkinter as ctk
from core.config import APP_NAME, APP_VERSION
from core.supabase_service import SupabaseService
from views.login_view import LoginView
from views.attendance_view import AttendanceView
from views.schedule_view import ScheduleView
from views.approval_view import ApprovalView
from views.report_view import ReportView
from views.settings_view import SettingsView

# Cấu hình giao diện CustomTkinter
ctk.set_appearance_mode("System")  # "Dark", "Light", "System"
ctk.set_default_color_theme("blue")  # Themes: "blue", "green", "dark-blue"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} - v{APP_VERSION}")
        self.geometry("1280x820")
        self.minsize(1100, 700)

        self.supabase = SupabaseService()
        self.current_profile = None

        # Container chính để chuyển đổi Single-Frame
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Khung ứng dụng sau khi đăng nhập (Bao gồm Sidebar + Main Content)
        self.main_app_frame = None
        self.sidebar_frame = None
        self.view_container = None
        self.current_view = None
        self.views = {}  # Cache các views để chuyển đổi tức thì (0ms lag)

        # Bắt đầu với Màn hình Đăng nhập
        self.show_login_view()

    def show_login_view(self):
        self.clear_container()
        self.current_profile = None
        self.views = {}
        login_view = LoginView(self.container, on_login_success=self.on_login_success)
        login_view.pack(fill="both", expand=True)

    def on_login_success(self, profile):
        self.current_profile = profile
        self.views = {}
        self.setup_main_layout()
        self.show_view("attendance")

    def setup_main_layout(self):
        self.clear_container()

        # Layout 2 cột: Sidebar trái (230px) + View Container phải
        self.main_app_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.main_app_frame.pack(fill="both", expand=True)

        self.sidebar_frame = ctk.CTkFrame(self.main_app_frame, width=230, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar_frame.pack_propagate(False)

        # Logo / Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="💊 NHÀ THUỐC", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.logo_label.pack(pady=(25, 15), padx=20)

        # Role Badge
        role = self.current_profile.get("role", "staff")
        role_label = {
            "admin": "👑 CHỦ CHUỖI",
            "storemanager": "👔 CỬA HÀNG TRƯỞNG",
            "staff": "💊 DƯỢC SĨ"
        }.get(role, role.upper())

        self.role_badge = ctk.CTkLabel(
            self.sidebar_frame, 
            text=role_label, 
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("#E5F2FF", "#18324F"),
            corner_radius=6,
            height=28
        )
        self.role_badge.pack(fill="x", padx=20, pady=(0, 20))

        # Menu buttons
        self.nav_buttons = {}

        self.add_nav_button("attendance", "🕒  Điểm danh quầy", self.show_attendance_view)
        self.add_nav_button("schedule", "📅  Lịch làm việc", self.show_schedule_view)

        # Menu cho Store Manager & Admin
        if role in ("storemanager", "admin"):
            self.add_nav_button("approval", "📋  Duyệt yêu cầu", self.show_approval_view)
            self.add_nav_button("reports", "📊  Báo cáo Excel", self.show_reports_view)

        # Menu chỉ cho Admin
        if role == "admin":
            self.add_nav_button("settings", "⚙️  Quản trị hệ thống", self.show_settings_view)

        # Spacer
        self.spacer = ctk.CTkLabel(self.sidebar_frame, text="")
        self.spacer.pack(fill="both", expand=True)

        # Nút Đăng xuất ở chân Sidebar
        self.logout_sidebar_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="🚪  Đăng xuất",
            fg_color="transparent",
            text_color="#FF4C4C",
            hover_color=("#FDE8E8", "#3E1E1E"),
            anchor="w",
            height=40,
            command=self.show_login_view
        )
        self.logout_sidebar_btn.pack(fill="x", padx=15, pady=(0, 20))

        # Khung hiển thị nội dung bên phải
        self.view_container = ctk.CTkFrame(self.main_app_frame, fg_color="transparent")
        self.view_container.pack(side="right", fill="both", expand=True)

    def add_nav_button(self, key, text, command):
        btn = ctk.CTkButton(
            self.sidebar_frame,
            text=text,
            font=ctk.CTkFont(size=13),
            anchor="w",
            height=42,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray85", "gray25"),
            corner_radius=8,
            command=command
        )
        btn.pack(fill="x", padx=15, pady=4)
        self.nav_buttons[key] = btn

    def set_active_nav(self, active_key):
        for key, btn in self.nav_buttons.items():
            if key == active_key:
                btn.configure(
                    fg_color=("#3B8ED0", "#1F6AA5"),
                    text_color="white",
                    font=ctk.CTkFont(size=13, weight="bold")
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("gray10", "gray90"),
                    font=ctk.CTkFont(size=13)
                )

    def clear_view_container(self):
        if self.current_view:
            self.current_view.pack_forget()
            self.current_view = None

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.pack_forget()
            widget.destroy()

    # ================= VIEW SWITCHING (TỨC THÌ QUA CACHE) =================
    def show_view(self, view_name):
        self.set_active_nav(view_name)
        if self.current_view:
            self.current_view.pack_forget()

        if view_name not in self.views:
            if view_name == "attendance":
                self.views["attendance"] = AttendanceView(
                    self.view_container,
                    current_profile=self.current_profile,
                    on_logout=self.show_login_view
                )
            elif view_name == "schedule":
                self.views["schedule"] = ScheduleView(
                    self.view_container,
                    current_profile=self.current_profile
                )
            elif view_name == "approval":
                self.views["approval"] = ApprovalView(
                    self.view_container,
                    current_profile=self.current_profile
                )
            elif view_name == "reports":
                self.views["reports"] = ReportView(
                    self.view_container,
                    current_profile=self.current_profile
                )
            elif view_name == "settings":
                self.views["settings"] = SettingsView(
                    self.view_container,
                    current_profile=self.current_profile
                )

        self.current_view = self.views.get(view_name)
        if self.current_view:
            self.current_view.pack(fill="both", expand=True)

    def show_attendance_view(self):
        self.show_view("attendance")

    def show_schedule_view(self):
        self.show_view("schedule")

    def show_approval_view(self):
        self.show_view("approval")

    def show_reports_view(self):
        self.show_view("reports")

    def show_settings_view(self):
        self.show_view("settings")

if __name__ == "__main__":
    app = App()
    app.mainloop()
