import threading
import customtkinter as ctk
from tkinter import messagebox
from core.hardware import get_hardware_uuid
from core.supabase_service import SupabaseService

class SettingsView(ctk.CTkFrame):
    def __init__(self, master, current_profile):
        super().__init__(master, fg_color="transparent")
        self.current_profile = current_profile
        self.supabase = SupabaseService()
        self.current_device_uuid = get_hardware_uuid()
        self.branch_map = {}
        self.branch_name_by_id = {}
        self._loaded_tabs = set()

        self.setup_ui()

    def setup_ui(self):
        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color=("white", "#242424"), height=60, corner_radius=12)
        self.header_frame.pack(fill="x", padx=20, pady=(20, 15))

        self.title_lbl = ctk.CTkLabel(
            self.header_frame, text="⚙️ CÀI ĐẶT HỆ THỐNG (CHỈ DÀNH CHO ADMIN)",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.title_lbl.pack(side="left", padx=20, pady=15)

        # Tabview cho 4 mục quản trị
        self.tabview = ctk.CTkTabview(self, corner_radius=12, command=self._on_tabview_change)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=0)

        self.tab_devices = self.tabview.add("Khóa máy quầy (Hardware UUID)")
        self.tab_branches = self.tabview.add("Chi nhánh")
        self.tab_shifts = self.tabview.add("Ca làm việc")
        self.tab_users = self.tabview.add("Nhân sự & Phân quyền")

        self.setup_devices_tab()
        self.setup_branches_tab()
        self.setup_shifts_tab()
        self.setup_users_tab()

        # Nạp dữ liệu Tab đầu tiên ngầm qua Worker Thread (0ms freeze)
        self._loaded_tabs.add("Khóa máy quầy (Hardware UUID)")
        self.load_devices_list()

    def _on_tabview_change(self):
        cur_tab = self.tabview.get()
        if cur_tab not in self._loaded_tabs:
            self._loaded_tabs.add(cur_tab)
            if cur_tab == "Chi nhánh":
                self.load_branches_list()
            elif cur_tab == "Ca làm việc":
                self.load_shifts_list()
            elif cur_tab == "Nhân sự & Phân quyền":
                self.load_users_list()

    def refresh_branch_cache(self):
        branches = self.supabase.get_branches(force_refresh=True)
        self.branch_map = {b["name"]: b["id"] for b in branches}
        self.branch_name_by_id = {b["id"]: b["name"] for b in branches}
        return branches

    # =========================================================================
    # TAB 1: KHÓA MÁY THIẾT BỊ (HARDWARE UUID) - FULL CRUD
    # =========================================================================
    def setup_devices_tab(self):
        # Card đăng ký máy tính
        box = ctk.CTkFrame(self.tab_devices, fg_color=("white", "#242424"), corner_radius=10)
        box.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            box, text="💻 ĐĂNG KÝ MÁY TÍNH QUẦY VÀO HỆ THỐNG", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 5))

        # Hiển thị UUID hiện tại
        uuid_frame = ctk.CTkFrame(box, fg_color="transparent")
        uuid_frame.pack(fill="x", padx=15, pady=(0, 10))

        uuid_lbl = ctk.CTkLabel(
            uuid_frame, 
            text=f"Mã Motherboard UUID máy này: {self.current_device_uuid}", 
            font=ctk.CTkFont(family="Consolas", size=12), 
            text_color="#3B8ED0"
        )
        uuid_lbl.pack(side="left")

        btn_copy = ctk.CTkButton(
            uuid_frame, text="📋 Sao chép UUID", width=110, height=24,
            fg_color="gray50", hover_color="gray40", font=ctk.CTkFont(size=11),
            command=self.copy_current_uuid
        )
        btn_copy.pack(side="left", padx=15)

        form_row = ctk.CTkFrame(box, fg_color="transparent")
        form_row.pack(fill="x", padx=15, pady=(0, 15))

        self.dev_branch_var = ctk.StringVar(value="Chọn Chi nhánh")
        self.dev_branch_menu = ctk.CTkOptionMenu(form_row, variable=self.dev_branch_var, width=190)
        self.dev_branch_menu.pack(side="left", padx=(0, 10))

        self.dev_name_entry = ctk.CTkEntry(form_row, placeholder_text="Tên máy (VD: Quầy Thu Ngân 1)", width=240)
        self.dev_name_entry.pack(side="left", padx=(0, 10))

        btn_reg = ctk.CTkButton(
            form_row, text="➕ Cấp phép máy này", fg_color="#28A745", hover_color="#218838",
            command=self.handle_register_current_device
        )
        btn_reg.pack(side="left", padx=(0, 10))

        btn_manual = ctk.CTkButton(
            form_row, text="➕ Thêm máy khác thủ công", fg_color="#17A2B8", hover_color="#138496",
            command=self.open_add_custom_device_modal
        )
        btn_manual.pack(side="left")

        # Danh sách thiết bị đã đăng ký
        self.scroll_devices = ctk.CTkScrollableFrame(self.tab_devices, fg_color="transparent")
        self.scroll_devices.pack(fill="both", expand=True, padx=10, pady=5)

    def copy_current_uuid(self):
        self.clipboard_clear()
        self.clipboard_append(self.current_device_uuid)
        messagebox.showinfo("Đã sao chép", "Đã sao chép mã Motherboard UUID vào bộ nhớ tạm!")

    def load_devices_list(self):
        for widget in self.scroll_devices.winfo_children():
            widget.destroy()

        loading_lbl = ctk.CTkLabel(self.scroll_devices, text="⏳ Đang tải danh sách máy quầy cấp phép...", text_color="gray")
        loading_lbl.pack(pady=20)

        def worker():
            branches = self.refresh_branch_cache()
            devices = self.supabase.get_allowed_devices()
            try:
                self.after(0, self._render_devices_ui, branches, devices)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _render_devices_ui(self, branches, devices):
        for widget in self.scroll_devices.winfo_children():
            widget.destroy()

        b_names = list(self.branch_map.keys())
        if b_names:
            self.dev_branch_menu.configure(values=b_names)
            if self.dev_branch_var.get() not in b_names:
                self.dev_branch_var.set(b_names[0])

        if not devices:
            ctk.CTkLabel(self.scroll_devices, text="Chưa có thiết bị nào được cấp phép trong hệ thống.", text_color="gray").pack(pady=20)
            return

        for dev in devices:
            row = ctk.CTkFrame(self.scroll_devices, fg_color=("white", "#242424"), corner_radius=8)
            row.pack(fill="x", pady=4)

            b_name = dev.get("branches", {}).get("name", "Chưa gán") if dev.get("branches") else "Chưa gán"
            d_name = dev.get("device_name", "Thiết bị không tên")
            d_uuid = dev.get("device_uuid", "")
            is_active = dev.get("is_active", True)
            is_current = (d_uuid == self.current_device_uuid)

            # Cột trái: Tên máy, chi nhánh, tag máy hiện tại
            left_info = ctk.CTkFrame(row, fg_color="transparent")
            left_info.pack(side="left", padx=15, pady=8)

            title_txt = f"🖥️ {d_name}  •  🏥 {b_name}"
            lbl_title = ctk.CTkLabel(left_info, text=title_txt, font=ctk.CTkFont(size=13, weight="bold"))
            lbl_title.pack(anchor="w")

            status_txt = "🟢 Đang hoạt động" if is_active else "🔴 Đã tạm khóa"
            uuid_display = f"UUID: {d_uuid}" + ("  ★ [MÁY NÀY]" if is_current else "") + f"  •  {status_txt}"
            lbl_sub = ctk.CTkLabel(
                left_info, text=uuid_display, 
                font=ctk.CTkFont(family="Consolas", size=11), 
                text_color="#28A745" if is_current else "gray"
            )
            lbl_sub.pack(anchor="w")

            # Cột phải: Nút Sửa, Xóa
            right_actions = ctk.CTkFrame(row, fg_color="transparent")
            right_actions.pack(side="right", padx=15, pady=8)

            btn_del = ctk.CTkButton(
                right_actions, text="🗑️ Xóa", width=70, height=28, 
                fg_color="#DC3545", hover_color="#C82333",
                command=lambda d=dev: self.handle_delete_device(d)
            )
            btn_del.pack(side="right", padx=(5, 0))

            btn_edit = ctk.CTkButton(
                right_actions, text="✏️ Sửa", width=70, height=28, 
                fg_color="#3B8ED0", hover_color="#1F6AA5",
                command=lambda d=dev: self.open_edit_device_modal(d)
            )
            btn_edit.pack(side="right", padx=5)

    def handle_register_current_device(self):
        b_name = self.dev_branch_var.get()
        branch_id = self.branch_map.get(b_name)
        dev_name = self.dev_name_entry.get().strip()

        if not branch_id or not dev_name:
            messagebox.showwarning("Lưu ý", "Vui lòng chọn Chi nhánh và nhập Tên máy!")
            return

        res = self.supabase.register_device(branch_id, self.current_device_uuid, dev_name)
        if res.get("success"):
            messagebox.showinfo("Thành công", f"Đã cấp phép máy '{dev_name}' cho chi nhánh {b_name}!")
            self.dev_name_entry.delete(0, "end")
            self.load_devices_list()
        else:
            messagebox.showerror("Thông báo", res.get("message", "Không thể cấp phép thiết bị."))

    def open_add_custom_device_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Thêm Máy Tính Thủ Công (Hardware UUID)")
        modal.geometry("450x380")
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        ctk.CTkLabel(modal, text="➕ THÊM MÁY TÍNH QUẦY KHÁC", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 15))

        # Chi nhánh
        ctk.CTkLabel(modal, text="Chọn Chi nhánh phân công:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        b_names = list(self.branch_map.keys())
        if not b_names:
            messagebox.showwarning("Lưu ý", "Chưa có chi nhánh nào! Vui lòng tạo chi nhánh trước.", parent=modal)
            modal.destroy()
            return

        b_var = ctk.StringVar(value=b_names[0])
        b_menu = ctk.CTkOptionMenu(modal, variable=b_var, values=b_names)
        b_menu.pack(fill="x", padx=30, pady=(0, 10))

        # Tên máy
        ctk.CTkLabel(modal, text="Tên máy nhận diện:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        name_entry = ctk.CTkEntry(modal, placeholder_text="VD: Máy Quầy Thu Ngân 2")
        name_entry.pack(fill="x", padx=30, pady=(0, 10))

        # UUID
        ctk.CTkLabel(modal, text="Motherboard UUID của máy quầy:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        uuid_entry = ctk.CTkEntry(modal, placeholder_text="VD: 45508223-B414-8545-88EF-EBCBD71CD861")
        uuid_entry.pack(fill="x", padx=30, pady=(0, 20))

        def save():
            b_id = self.branch_map.get(b_var.get())
            d_name = name_entry.get().strip()
            d_uuid = uuid_entry.get().strip()

            if not b_id or not d_name or not d_uuid:
                messagebox.showwarning("Lưu ý", "Vui lòng nhập đầy đủ Chi nhánh, Tên máy và mã UUID!", parent=modal)
                return

            res = self.supabase.register_device(b_id, d_uuid, d_name)
            if res.get("success"):
                messagebox.showinfo("Thành công", f"Đã đăng ký máy '{d_name}' vào hệ thống!", parent=modal)
                modal.destroy()
                self.load_devices_list()
            else:
                messagebox.showerror("Thông báo", res.get("message", "Không thể lưu thiết bị."), parent=modal)

        ctk.CTkButton(modal, text="💾 LƯU MÁY TÍNH", height=38, fg_color="#28A745", hover_color="#218838", command=save).pack(fill="x", padx=30)

    def open_edit_device_modal(self, dev):
        modal = ctk.CTkToplevel(self)
        modal.title(f"Sửa Thiết Bị - {dev.get('device_name')}")
        modal.geometry("450x380")
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"✏️ CHỈNH SỬA MÁY: {dev.get('device_name')}", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 15))

        # Chi nhánh
        ctk.CTkLabel(modal, text="Chi nhánh:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        b_names = list(self.branch_map.keys())
        cur_b_name = self.branch_name_by_id.get(dev.get("branch_id"), b_names[0] if b_names else "")
        b_var = ctk.StringVar(value=cur_b_name)
        b_menu = ctk.CTkOptionMenu(modal, variable=b_var, values=b_names)
        b_menu.pack(fill="x", padx=30, pady=(0, 10))

        # Tên máy
        ctk.CTkLabel(modal, text="Tên máy:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        name_entry = ctk.CTkEntry(modal)
        name_entry.insert(0, dev.get("device_name", ""))
        name_entry.pack(fill="x", padx=30, pady=(0, 10))

        # Trạng thái hoạt động
        status_var = ctk.BooleanVar(value=dev.get("is_active", True))
        status_switch = ctk.CTkSwitch(modal, text="Kích hoạt (Cho phép máy này điểm danh)", variable=status_var)
        status_switch.pack(anchor="w", padx=30, pady=(5, 20))

        def save():
            b_id = self.branch_map.get(b_var.get())
            d_name = name_entry.get().strip()
            is_active = status_var.get()

            if not b_id or not d_name:
                messagebox.showwarning("Lưu ý", "Tên máy và Chi nhánh không được để trống!", parent=modal)
                return

            res = self.supabase.update_device(dev.get("id"), b_id, d_name, is_active)
            if res.get("success"):
                messagebox.showinfo("Thành công", "Đã cập nhật thông tin thiết bị!", parent=modal)
                modal.destroy()
                self.load_devices_list()
            else:
                messagebox.showerror("Thông báo", res.get("message", "Không thể cập nhật thiết bị."), parent=modal)

        ctk.CTkButton(modal, text="💾 LƯU THAY ĐỔI", height=38, fg_color="#28A745", hover_color="#218838", command=save).pack(fill="x", padx=30)

    def handle_delete_device(self, dev):
        d_name = dev.get("device_name", "")
        if messagebox.askyesno("Xác nhận xóa", f"Hủy cấp phép và xóa máy '{d_name}' khỏi hệ thống?\nNhân viên tại quầy này sẽ không thể điểm danh nếu không có máy khác được cấp phép."):
            res = self.supabase.delete_device(dev.get("id"))
            if res.get("success"):
                messagebox.showinfo("Thành công", f"Đã xóa máy '{d_name}'!")
                self.load_devices_list()
            else:
                messagebox.showerror("Thông báo", res.get("message", "Không thể xóa thiết bị."))

    # =========================================================================
    # TAB 2: QUẢN LÝ CHI NHÁNH (BRANCHES) - FULL CRUD
    # =========================================================================
    def setup_branches_tab(self):
        box = ctk.CTkFrame(self.tab_branches, fg_color=("white", "#242424"), corner_radius=10)
        box.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(box, text="🏥 THÊM CHI NHÁNH NHÀ THUỐC MỚI", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))

        form_row = ctk.CTkFrame(box, fg_color="transparent")
        form_row.pack(fill="x", padx=15, pady=(0, 15))

        self.b_name_entry = ctk.CTkEntry(form_row, placeholder_text="Tên chi nhánh (VD: Nhà thuốc CS2 - Bình Thạnh)", width=280)
        self.b_name_entry.pack(side="left", padx=(0, 10))

        self.b_addr_entry = ctk.CTkEntry(form_row, placeholder_text="Địa chỉ", width=320)
        self.b_addr_entry.pack(side="left", padx=(0, 10))

        btn_add = ctk.CTkButton(form_row, text="➕ Tạo chi nhánh", fg_color="#28A745", hover_color="#218838", command=self.handle_add_branch)
        btn_add.pack(side="left")

        self.scroll_branches = ctk.CTkScrollableFrame(self.tab_branches, fg_color="transparent")
        self.scroll_branches.pack(fill="both", expand=True, padx=10, pady=5)

    def load_branches_list(self):
        for widget in self.scroll_branches.winfo_children():
            widget.destroy()

        loading_lbl = ctk.CTkLabel(self.scroll_branches, text="⏳ Đang tải danh sách chi nhánh...", text_color="gray")
        loading_lbl.pack(pady=20)

        def worker():
            branches = self.refresh_branch_cache()
            sm_map = {}
            if branches:
                for b in branches:
                    b_id = b.get("id")
                    sm = self.supabase.get_branch_storemanager(b_id)
                    sm_map[b_id] = sm
            try:
                self.after(0, self._render_branches_ui, branches, sm_map)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _render_branches_ui(self, branches, sm_map):
        for widget in self.scroll_branches.winfo_children():
            widget.destroy()

        if not branches:
            ctk.CTkLabel(self.scroll_branches, text="Chưa có chi nhánh nào trong hệ thống.", text_color="gray").pack(pady=20)
            return

        for b in branches:
            row = ctk.CTkFrame(self.scroll_branches, fg_color=("white", "#242424"), corner_radius=8)
            row.pack(fill="x", pady=4)

            name = b.get("name", "")
            addr = b.get("address", "") or "Chưa có địa chỉ"
            b_id = b.get("id")

            # Kiểm tra Cửa hàng trưởng hiện tại của chi nhánh
            sm = sm_map.get(b_id)
            sm_txt = f"👑 Quản lý: {sm.get('full_name')}" if sm else "⚠️ Chưa có Quản lý chi nhánh"

            left_box = ctk.CTkFrame(row, fg_color="transparent")
            left_box.pack(side="left", padx=15, pady=8)

            lbl_title = ctk.CTkLabel(left_box, text=f"🏥 {name}", font=ctk.CTkFont(size=13, weight="bold"))
            lbl_title.pack(anchor="w")

            lbl_sub = ctk.CTkLabel(
                left_box, text=f"📍 {addr}   •   {sm_txt}", 
                font=ctk.CTkFont(size=11), 
                text_color="#6F42C1" if sm else "gray"
            )
            lbl_sub.pack(anchor="w")

            right_actions = ctk.CTkFrame(row, fg_color="transparent")
            right_actions.pack(side="right", padx=15, pady=8)

            btn_del = ctk.CTkButton(
                right_actions, text="🗑️ Xóa", width=70, height=28, 
                fg_color="#DC3545", hover_color="#C82333",
                command=lambda br=b: self.handle_delete_branch(br)
            )
            btn_del.pack(side="right", padx=(5, 0))

            btn_edit = ctk.CTkButton(
                right_actions, text="✏️ Sửa", width=70, height=28, 
                fg_color="#3B8ED0", hover_color="#1F6AA5",
                command=lambda br=b: self.open_edit_branch_modal(br)
            )
            btn_edit.pack(side="right", padx=5)

    def handle_add_branch(self):
        name = self.b_name_entry.get().strip()
        addr = self.b_addr_entry.get().strip()
        if not name:
            messagebox.showwarning("Lưu ý", "Tên chi nhánh không được để trống!")
            return

        res = self.supabase.create_branch(name, addr)
        if res.get("success"):
            messagebox.showinfo("Thành công", f"Đã thêm chi nhánh '{name}'!")
            self.b_name_entry.delete(0, "end")
            self.b_addr_entry.delete(0, "end")
            self.load_branches_list()
            self.load_devices_list()
            self.load_shifts_list()
        else:
            messagebox.showerror("Thông báo", res.get("message", "Không thể tạo chi nhánh."))

    def open_edit_branch_modal(self, br):
        modal = ctk.CTkToplevel(self)
        modal.title(f"Sửa Chi Nhánh - {br.get('name')}")
        modal.geometry("450x300")
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"✏️ SỬA CHI NHÁNH", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 15))

        ctk.CTkLabel(modal, text="Tên chi nhánh:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        name_entry = ctk.CTkEntry(modal)
        name_entry.insert(0, br.get("name", ""))
        name_entry.pack(fill="x", padx=30, pady=(0, 10))

        ctk.CTkLabel(modal, text="Địa chỉ:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        addr_entry = ctk.CTkEntry(modal)
        addr_entry.insert(0, br.get("address", "") or "")
        addr_entry.pack(fill="x", padx=30, pady=(0, 20))

        def save():
            name = name_entry.get().strip()
            addr = addr_entry.get().strip()
            if not name:
                messagebox.showwarning("Lưu ý", "Tên chi nhánh không được để trống!", parent=modal)
                return

            res = self.supabase.update_branch(br.get("id"), name, addr)
            if res.get("success"):
                messagebox.showinfo("Thành công", "Đã cập nhật thông tin chi nhánh!", parent=modal)
                modal.destroy()
                self.load_branches_list()
                self.load_devices_list()
            else:
                messagebox.showerror("Thông báo", res.get("message", "Không thể cập nhật chi nhánh."), parent=modal)

        ctk.CTkButton(modal, text="💾 LƯU THAY ĐỔI", height=38, fg_color="#28A745", hover_color="#218838", command=save).pack(fill="x", padx=30)

    def handle_delete_branch(self, br):
        name = br.get("name", "")
        if messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa chi nhánh '{name}'?\nLưu ý: Nếu chi nhánh đang có máy tính, ca làm việc hoặc nhân sự thì cần chuyển hoặc xóa các mục đó trước."):
            res = self.supabase.delete_branch(br.get("id"))
            if res.get("success"):
                messagebox.showinfo("Thành công", f"Đã xóa chi nhánh '{name}'!")
                self.load_branches_list()
                self.load_devices_list()
            else:
                messagebox.showerror("Thông báo", res.get("message", "Không thể xóa chi nhánh."))

    # =========================================================================
    # TAB 3: QUẢN LÝ CA LÀM VIỆC (SHIFTS) - FULL CRUD
    # =========================================================================
    def setup_shifts_tab(self):
        box = ctk.CTkFrame(self.tab_shifts, fg_color=("white", "#242424"), corner_radius=10)
        box.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(box, text="⏰ TẠO CA LÀM VIỆC CHO CHI NHÁNH", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))

        form_row = ctk.CTkFrame(box, fg_color="transparent")
        form_row.pack(fill="x", padx=15, pady=(0, 15))

        self.shift_branch_var = ctk.StringVar(value="Chọn Chi nhánh")
        self.shift_branch_menu = ctk.CTkOptionMenu(form_row, variable=self.shift_branch_var, width=180)
        self.shift_branch_menu.pack(side="left", padx=(0, 10))

        self.shift_name_entry = ctk.CTkEntry(form_row, placeholder_text="Tên ca (VD: Ca Sáng)", width=150)
        self.shift_name_entry.pack(side="left", padx=(0, 10))

        self.shift_start_entry = ctk.CTkEntry(form_row, placeholder_text="08:00:00", width=95)
        self.shift_start_entry.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(form_row, text="đến").pack(side="left", padx=4)

        self.shift_end_entry = ctk.CTkEntry(form_row, placeholder_text="16:00:00", width=95)
        self.shift_end_entry.pack(side="left", padx=(5, 10))

        btn_add = ctk.CTkButton(form_row, text="➕ Tạo Ca", fg_color="#28A745", hover_color="#218838", command=self.handle_add_shift)
        btn_add.pack(side="left")

        self.scroll_shifts = ctk.CTkScrollableFrame(self.tab_shifts, fg_color="transparent")
        self.scroll_shifts.pack(fill="both", expand=True, padx=10, pady=5)

    def load_shifts_list(self):
        for widget in self.scroll_shifts.winfo_children():
            widget.destroy()

        loading_lbl = ctk.CTkLabel(self.scroll_shifts, text="⏳ Đang tải danh sách ca làm việc...", text_color="gray")
        loading_lbl.pack(pady=20)

        def worker():
            branches = self.refresh_branch_cache()
            shifts = self.supabase.get_shifts(force_refresh=True)
            try:
                self.after(0, self._render_shifts_ui, branches, shifts)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _render_shifts_ui(self, branches, shifts):
        for widget in self.scroll_shifts.winfo_children():
            widget.destroy()

        b_names = list(self.branch_map.keys())
        if b_names:
            self.shift_branch_menu.configure(values=b_names)
            if self.shift_branch_var.get() not in b_names:
                self.shift_branch_var.set(b_names[0])

        if not shifts:
            ctk.CTkLabel(self.scroll_shifts, text="Chưa có ca làm việc nào.", text_color="gray").pack(pady=20)
            return

        for s in shifts:
            row = ctk.CTkFrame(self.scroll_shifts, fg_color=("white", "#242424"), corner_radius=8)
            row.pack(fill="x", pady=4)

            name = s.get("name", "")
            st = s.get("start_time", "")[:5]
            et = s.get("end_time", "")[:5]
            b_name = s.get("branches", {}).get("name", "Chưa gán") if s.get("branches") else "Tất cả chi nhánh"

            left_box = ctk.CTkFrame(row, fg_color="transparent")
            left_box.pack(side="left", padx=15, pady=8)

            lbl_title = ctk.CTkLabel(left_box, text=f"⏰ {name}   ({st} - {et})", font=ctk.CTkFont(size=13, weight="bold"))
            lbl_title.pack(anchor="w")

            lbl_sub = ctk.CTkLabel(left_box, text=f"🏥 Chi nhánh: {b_name}", font=ctk.CTkFont(size=11), text_color="gray")
            lbl_sub.pack(anchor="w")

            right_actions = ctk.CTkFrame(row, fg_color="transparent")
            right_actions.pack(side="right", padx=15, pady=8)

            btn_del = ctk.CTkButton(
                right_actions, text="🗑️ Xóa", width=70, height=28, 
                fg_color="#DC3545", hover_color="#C82333",
                command=lambda sh=s: self.handle_delete_shift(sh)
            )
            btn_del.pack(side="right", padx=(5, 0))

            btn_edit = ctk.CTkButton(
                right_actions, text="✏️ Sửa", width=70, height=28, 
                fg_color="#3B8ED0", hover_color="#1F6AA5",
                command=lambda sh=s: self.open_edit_shift_modal(sh)
            )
            btn_edit.pack(side="right", padx=5)

    def handle_add_shift(self):
        b_name = self.shift_branch_var.get()
        b_id = self.branch_map.get(b_name)
        s_name = self.shift_name_entry.get().strip()
        st = self.shift_start_entry.get().strip()
        et = self.shift_end_entry.get().strip()

        if not s_name or not st or not et:
            messagebox.showwarning("Lưu ý", "Vui lòng nhập đầy đủ Tên ca và Giờ bắt đầu/kết thúc (VD: 08:00:00)!")
            return

        res = self.supabase.create_shift(b_id, s_name, st, et)
        if res.get("success"):
            messagebox.showinfo("Thành công", f"Đã tạo ca '{s_name}'!")
            self.shift_name_entry.delete(0, "end")
            self.load_shifts_list()
        else:
            messagebox.showerror("Thông báo", res.get("message", "Không thể tạo ca làm việc."))

    def open_edit_shift_modal(self, shift):
        modal = ctk.CTkToplevel(self)
        modal.title(f"Sửa Ca - {shift.get('name')}")
        modal.geometry("450x360")
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"✏️ SỬA CA LÀM VIỆC", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 15))

        # Chi nhánh
        ctk.CTkLabel(modal, text="Chi nhánh áp dụng:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        b_names = list(self.branch_map.keys())
        cur_b_name = self.branch_name_by_id.get(shift.get("branch_id"), b_names[0] if b_names else "")
        b_var = ctk.StringVar(value=cur_b_name)
        b_menu = ctk.CTkOptionMenu(modal, variable=b_var, values=b_names)
        b_menu.pack(fill="x", padx=30, pady=(0, 10))

        # Tên ca
        ctk.CTkLabel(modal, text="Tên ca:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        name_entry = ctk.CTkEntry(modal)
        name_entry.insert(0, shift.get("name", ""))
        name_entry.pack(fill="x", padx=30, pady=(0, 10))

        # Giờ bắt đầu & kết thúc
        time_row = ctk.CTkFrame(modal, fg_color="transparent")
        time_row.pack(fill="x", padx=30, pady=(5, 20))

        ctk.CTkLabel(time_row, text="Bắt đầu:").pack(side="left")
        st_entry = ctk.CTkEntry(time_row, width=100)
        st_entry.insert(0, shift.get("start_time", "")[:8])
        st_entry.pack(side="left", padx=(5, 15))

        ctk.CTkLabel(time_row, text="Kết thúc:").pack(side="left")
        et_entry = ctk.CTkEntry(time_row, width=100)
        et_entry.insert(0, shift.get("end_time", "")[:8])
        et_entry.pack(side="left", padx=5)

        def save():
            b_id = self.branch_map.get(b_var.get())
            name = name_entry.get().strip()
            st = st_entry.get().strip()
            et = et_entry.get().strip()

            if not name or not st or not et:
                messagebox.showwarning("Lưu ý", "Vui lòng nhập đầy đủ Tên ca và Giờ!", parent=modal)
                return

            res = self.supabase.update_shift(shift.get("id"), b_id, name, st, et)
            if res.get("success"):
                messagebox.showinfo("Thành công", "Đã cập nhật ca làm việc!", parent=modal)
                modal.destroy()
                self.load_shifts_list()
            else:
                messagebox.showerror("Thông báo", res.get("message", "Không thể cập nhật ca làm việc."), parent=modal)

        ctk.CTkButton(modal, text="💾 LƯU THAY ĐỔI", height=38, fg_color="#28A745", hover_color="#218838", command=save).pack(fill="x", padx=30)

    def handle_delete_shift(self, shift):
        name = shift.get("name", "")
        if messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa ca làm việc '{name}'?"):
            res = self.supabase.delete_shift(shift.get("id"))
            if res.get("success"):
                messagebox.showinfo("Thành công", f"Đã xóa ca '{name}'!")
                self.load_shifts_list()
            else:
                messagebox.showerror("Thông báo", res.get("message", "Không thể xóa ca làm việc."))

    # =========================================================================
    # TAB 4: QUẢN LÝ NHÂN SỰ & PHÂN QUYỀN - FULL CRUD + 1 ADMIN + 1 SM / CN
    # =========================================================================
    def setup_users_tab(self):
        # Action Bar trên cùng
        top_bar = ctk.CTkFrame(self.tab_users, fg_color=("white", "#242424"), corner_radius=10)
        top_bar.pack(fill="x", padx=10, pady=10)

        self.users_count_lbl = ctk.CTkLabel(
            top_bar, text="👥 Quản lý nhân viên toàn chuỗi (Quy tắc: 1 Admin tối cao, mỗi chi nhánh chỉ có 1 Cửa hàng trưởng)",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.users_count_lbl.pack(side="left", padx=15, pady=12)

        btn_create_user = ctk.CTkButton(
            top_bar, text="➕ TẠO TÀI KHOẢN NHÂN VIÊN MỚI", 
            fg_color="#28A745", hover_color="#218838",
            height=36, font=ctk.CTkFont(size=13, weight="bold"),
            command=self.open_create_user_modal
        )
        btn_create_user.pack(side="right", padx=15, pady=8)

        self.scroll_users = ctk.CTkScrollableFrame(self.tab_users, fg_color="transparent")
        self.scroll_users.pack(fill="both", expand=True, padx=10, pady=5)

    def load_users_list(self):
        for widget in self.scroll_users.winfo_children():
            widget.destroy()

        loading_lbl = ctk.CTkLabel(self.scroll_users, text="⏳ Đang tải danh sách nhân sự...", text_color="gray")
        loading_lbl.pack(pady=20)

        def worker():
            self.refresh_branch_cache()
            users = self.supabase.get_staff_list(force_refresh=True)
            try:
                self.after(0, self._render_users_ui, users)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _render_users_ui(self, users):
        for widget in self.scroll_users.winfo_children():
            widget.destroy()

        if not users:
            ctk.CTkLabel(self.scroll_users, text="Chưa có nhân viên nào trong cơ sở dữ liệu.", text_color="gray").pack(pady=20)
            return

        self.users_count_lbl.configure(text=f"👥 Tổng cộng: {len(users)} nhân sự  •  Hệ thống: Duy nhất 1 Admin tối cao, mỗi CN tối đa 1 Quản lý")

        for u in users:
            row = ctk.CTkFrame(self.scroll_users, fg_color=("white", "#242424"), corner_radius=8)
            row.pack(fill="x", pady=4)

            name = u.get("full_name", "")
            role = u.get("role", "staff").lower()
            b_name = u.get("branches", {}).get("name", "Chưa gán chi nhánh") if u.get("branches") else "Chưa gán chi nhánh"
            phone = u.get("phone", "") or "Chưa có SĐT"
            active = u.get("is_active", True)
            is_admin = (role == "admin")

            # Cột thông tin nhân viên
            left_info = ctk.CTkFrame(row, fg_color="transparent")
            left_info.pack(side="left", padx=15, pady=8)

            # Badge Vai trò
            if is_admin:
                role_label = "[👑 ADMIN CHỦ CHUỖI]"
                role_color = "#DC3545"
            elif role == "storemanager":
                role_label = "[⭐ CỬA HÀNG TRƯỞNG]"
                role_color = "#6F42C1"
            else:
                role_label = "[💊 DƯỢC SĨ QUẦY]"
                role_color = "#0D6EFD"

            status_str = "🟢 Hoạt động" if active else "🔴 Đã tạm khóa"

            title_txt = f"👤 {name}   {role_label}"
            lbl_title = ctk.CTkLabel(left_info, text=title_txt, font=ctk.CTkFont(size=13, weight="bold"), text_color=role_color if is_admin else None)
            lbl_title.pack(anchor="w")

            sub_txt = f"🏥 {b_name}   •   📞 {phone}   •   {status_str}"
            lbl_sub = ctk.CTkLabel(left_info, text=sub_txt, font=ctk.CTkFont(size=11), text_color="gray")
            lbl_sub.pack(anchor="w")

            # Cột actions: Sửa, Xóa (Bảo vệ tài khoản Admin tuyệt đối)
            right_actions = ctk.CTkFrame(row, fg_color="transparent")
            right_actions.pack(side="right", padx=15, pady=8)

            if is_admin:
                ctk.CTkLabel(
                    right_actions, text="🛡️ Tài khoản gốc (Bảo vệ)", 
                    font=ctk.CTkFont(size=12, weight="bold"), text_color="#DC3545"
                ).pack(side="right", padx=10)
            else:
                btn_del = ctk.CTkButton(
                    right_actions, text="🗑️ Xóa", width=70, height=28, 
                    fg_color="#DC3545", hover_color="#C82333",
                    command=lambda usr=u: self.handle_delete_user(usr)
                )
                btn_del.pack(side="right", padx=(5, 0))

                btn_edit = ctk.CTkButton(
                    right_actions, text="✏️ Sửa & Quyền", width=110, height=28, 
                    fg_color="#3B8ED0", hover_color="#1F6AA5",
                    command=lambda usr=u: self.open_edit_user_modal(usr)
                )
                btn_edit.pack(side="right", padx=5)

    def open_create_user_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Tạo Tài Khoản Nhân Viên Mới")
        modal.geometry("480x520")
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        ctk.CTkLabel(modal, text="➕ TẠO TÀI KHOẢN NHÂN VIÊN MỚI", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 15))

        # Họ tên
        ctk.CTkLabel(modal, text="Họ và tên nhân viên:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        name_entry = ctk.CTkEntry(modal, placeholder_text="VD: Nguyễn Văn A")
        name_entry.pack(fill="x", padx=30, pady=(0, 8))

        # Email / Tên đăng nhập
        ctk.CTkLabel(modal, text="Tên đăng nhập hoặc Email:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        email_entry = ctk.CTkEntry(modal, placeholder_text="VD: duocsi1 (hoặc duocsi1@nhathuoc.com)")
        email_entry.pack(fill="x", padx=30, pady=(0, 8))

        # Mật khẩu
        ctk.CTkLabel(modal, text="Mật khẩu khởi tạo:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        pass_entry = ctk.CTkEntry(modal, show="*", placeholder_text="Nhập mật khẩu (tối thiểu 6 ký tự)")
        pass_entry.insert(0, "123456")
        pass_entry.pack(fill="x", padx=30, pady=(0, 8))

        # SĐT
        ctk.CTkLabel(modal, text="Số điện thoại liên hệ:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        phone_entry = ctk.CTkEntry(modal, placeholder_text="VD: 0912345678")
        phone_entry.pack(fill="x", padx=30, pady=(0, 8))

        # Chi nhánh
        ctk.CTkLabel(modal, text="Chi nhánh phân công:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        b_names = list(self.branch_map.keys())
        if not b_names:
            messagebox.showwarning("Lưu ý", "Chưa có chi nhánh nào! Vui lòng tạo chi nhánh trước.", parent=modal)
            modal.destroy()
            return
        branch_var = ctk.StringVar(value=b_names[0])
        branch_menu = ctk.CTkOptionMenu(modal, variable=branch_var, values=b_names)
        branch_menu.pack(fill="x", padx=30, pady=(0, 8))

        # Vai trò (Role) - CHỈ CHO PHÉP STAFF HOẶC STOREMANAGER (Chỉ 1 Admin duy nhất)
        ctk.CTkLabel(modal, text="Vai trò trong hệ thống:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        role_choices = {
            "💊 Dược sĩ quầy (staff)": "staff",
            "⭐ Cửa hàng trưởng (storemanager)": "storemanager"
        }
        role_var = ctk.StringVar(value="💊 Dược sĩ quầy (staff)")
        role_menu = ctk.CTkOptionMenu(modal, variable=role_var, values=list(role_choices.keys()))
        role_menu.pack(fill="x", padx=30, pady=(0, 20))

        def save():
            full_name = name_entry.get().strip()
            raw_email = email_entry.get().strip()
            password = pass_entry.get().strip()
            phone = phone_entry.get().strip()
            chosen_b = branch_var.get()
            branch_id = self.branch_map.get(chosen_b)
            role = role_choices.get(role_var.get(), "staff")

            if not full_name or not raw_email or not password:
                messagebox.showwarning("Lưu ý", "Vui lòng nhập Họ tên, Tên đăng nhập và Mật khẩu!", parent=modal)
                return

            if len(password) < 6:
                messagebox.showwarning("Lưu ý", "Mật khẩu phải có độ dài tối thiểu 6 ký tự!", parent=modal)
                return

            # Chuẩn hóa email
            email = raw_email if "@" in raw_email else f"{raw_email}@nhathuoc.com"

            # RÀNG BUỘC: Mỗi chi nhánh chỉ được phép có DUY NHẤT 1 Cửa hàng trưởng
            if role == "storemanager":
                existing_sm = self.supabase.get_branch_storemanager(branch_id)
                if existing_sm:
                    messagebox.showerror(
                        "Ràng buộc Cửa hàng trưởng", 
                        f"Chi nhánh '{chosen_b}' hiện ĐÃ CÓ Cửa hàng trưởng là '{existing_sm.get('full_name')}'.\n\nMỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý!\nVui lòng chọn chi nhánh khác hoặc hạ quyền Cửa hàng trưởng hiện tại trước.", 
                        parent=modal
                    )
                    return

            res = self.supabase.create_user(email, password, full_name, role, branch_id, phone)
            if res.get("success"):
                messagebox.showinfo("Thành công", f"Đã tạo thành công tài khoản cho nhân viên {full_name}!\n\nTài khoản: {email}\nMật khẩu: {password}", parent=modal)
                modal.destroy()
                self.load_users_list()
            else:
                msg = res.get('message', 'Không thể tạo tài khoản nhân viên. Vui lòng liên hệ Quản trị viên hệ thống!')
                messagebox.showerror("Thông báo", msg, parent=modal)

        ctk.CTkButton(modal, text="💾 TẠO TÀI KHOẢN NGAY", height=40, fg_color="#28A745", hover_color="#218838", font=ctk.CTkFont(weight="bold"), command=save).pack(fill="x", padx=30)

    def open_edit_user_modal(self, user):
        modal = ctk.CTkToplevel(self)
        modal.title(f"Sửa & Phân Quyền - {user.get('full_name')}")
        modal.geometry("460x480")
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"✏️ SỬA NHÂN VIÊN & PHÂN QUYỀN", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 15))

        # Họ tên
        ctk.CTkLabel(modal, text="Họ và tên:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        name_entry = ctk.CTkEntry(modal)
        name_entry.insert(0, user.get("full_name", ""))
        name_entry.pack(fill="x", padx=30, pady=(0, 8))

        # SĐT
        ctk.CTkLabel(modal, text="Số điện thoại:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        phone_entry = ctk.CTkEntry(modal)
        phone_entry.insert(0, user.get("phone", "") or "")
        phone_entry.pack(fill="x", padx=30, pady=(0, 8))

        # Chi nhánh
        ctk.CTkLabel(modal, text="Chi nhánh phân công:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        b_names = list(self.branch_map.keys())
        cur_b_name = self.branch_name_by_id.get(user.get("branch_id"), b_names[0] if b_names else "")
        branch_var = ctk.StringVar(value=cur_b_name)
        branch_menu = ctk.CTkOptionMenu(modal, variable=branch_var, values=b_names)
        branch_menu.pack(fill="x", padx=30, pady=(0, 8))

        # Vai trò
        ctk.CTkLabel(modal, text="Vai trò:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30, pady=(5, 2))
        role_choices = {
            "💊 Dược sĩ quầy (staff)": "staff",
            "⭐ Cửa hàng trưởng (storemanager)": "storemanager"
        }
        cur_role = user.get("role", "staff").lower()
        default_role_label = "⭐ Cửa hàng trưởng (storemanager)" if cur_role == "storemanager" else "💊 Dược sĩ quầy (staff)"
        role_var = ctk.StringVar(value=default_role_label)
        role_menu = ctk.CTkOptionMenu(modal, variable=role_var, values=list(role_choices.keys()))
        role_menu.pack(fill="x", padx=30, pady=(0, 10))

        # Trạng thái
        status_var = ctk.BooleanVar(value=user.get("is_active", True))
        status_switch = ctk.CTkSwitch(modal, text="Kích hoạt tài khoản (Cho phép đăng nhập)", variable=status_var)
        status_switch.pack(anchor="w", padx=30, pady=(5, 20))

        def save():
            new_name = name_entry.get().strip()
            new_phone = phone_entry.get().strip()
            chosen_b = branch_var.get()
            new_b_id = self.branch_map.get(chosen_b)
            new_role = role_choices.get(role_var.get(), "staff")
            is_active = status_var.get()

            if not new_name:
                messagebox.showwarning("Lưu ý", "Họ tên không được để trống!", parent=modal)
                return

            # Kiểm tra ràng buộc Store Manager duy nhất nếu thay đổi hoặc phân bổ sang CN khác
            if new_role == "storemanager":
                existing_sm = self.supabase.get_branch_storemanager(new_b_id)
                if existing_sm and existing_sm.get("id") != user.get("id"):
                    messagebox.showerror(
                        "Ràng buộc Cửa hàng trưởng", 
                        f"Chi nhánh '{chosen_b}' đã có Cửa hàng trưởng là '{existing_sm.get('full_name')}'.\n\nMỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý!",
                        parent=modal
                    )
                    return

            res = self.supabase.update_user_full(
                user_id=user.get("id"),
                full_name=new_name,
                role=new_role,
                branch_id=new_b_id,
                phone=new_phone,
                is_active=is_active
            )
            if res.get("success"):
                messagebox.showinfo("Thành công", "Đã cập nhật thông tin và phân quyền nhân sự!", parent=modal)
                modal.destroy()
                self.load_users_list()
            else:
                messagebox.showerror("Thông báo", res.get("message", "Không thể cập nhật nhân sự."), parent=modal)

        ctk.CTkButton(modal, text="💾 LƯU THAY ĐỔI", height=38, fg_color="#28A745", hover_color="#218838", command=save).pack(fill="x", padx=30)

    def handle_delete_user(self, user):
        role = user.get("role", "staff").lower()
        name = user.get("full_name", "")
        if role == "admin":
            messagebox.showerror("Bị chặn", "Không thể xóa tài khoản Admin tối cao của hệ thống!")
            return

        if messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc chắn muốn xóa vĩnh viễn tài khoản nhân sự '{name}'?\nToàn bộ dữ liệu chấm công và lịch làm việc của nhân viên này sẽ bị xóa khỏi hệ thống."):
            res = self.supabase.delete_user_full(user.get("id"))
            if res.get("success"):
                messagebox.showinfo("Thành công", f"Đã xóa nhân viên '{name}'!")
                self.load_users_list()
            else:
                messagebox.showerror("Thông báo", res.get("message", "Không thể xóa nhân viên."))
