from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QFrame, QTabWidget, QScrollArea, QDialog, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
from core.hardware import get_hardware_uuid
from core.supabase_service import SupabaseService
from core.qt_worker import QtWorker

class SettingsView(QWidget):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent)
        self.current_profile = current_profile or {}
        self.supabase = SupabaseService()
        self.current_device_uuid = get_hardware_uuid()
        self.branch_map = {}
        self.branch_name_by_id = {}
        self._loaded_tabs = set()
        self.worker = None

        self.setup_ui()

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(15)

        # 1. Header
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 12px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 10, 20, 10)

        lbl_title = QLabel("⚙️ CÀI ĐẶT HỆ THỐNG (CHỈ DÀNH CHO ADMIN)")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; border: none;")
        h_layout.addWidget(lbl_title)
        h_layout.addStretch()
        root_layout.addWidget(header)

        # 2. Tab Widget (4 tabs)
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        self.setup_devices_tab()
        self.setup_branches_tab()
        self.setup_shifts_tab()
        self.setup_users_tab()

        root_layout.addWidget(self.tab_widget)

        # Tải ngầm tab 1 ban đầu
        self._loaded_tabs.add(0)
        self.load_devices_list()

    def _on_tab_changed(self, index):
        if index not in self._loaded_tabs:
            self._loaded_tabs.add(index)
            if index == 1:
                self.load_branches_list()
            elif index == 2:
                self.load_shifts_list()
            elif index == 3:
                self.load_users_list()

    def refresh_branch_cache(self):
        branches = self.supabase.get_branches(force_refresh=True)
        self.branch_map = {b["name"]: b["id"] for b in branches}
        self.branch_name_by_id = {b["id"]: b["name"] for b in branches}
        return branches

    # =========================================================================
    # TAB 1: KHÓA MÁY QUẦY (HARDWARE UUID)
    # =========================================================================
    def setup_devices_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Form Card
        box = QFrame()
        box.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px; padding: 15px;")
        b_layout = QVBoxLayout(box)
        b_layout.setSpacing(10)

        lbl_t = QLabel("💻 ĐĂNG KÝ MÁY TÍNH QUẦY VÀO HỆ THỐNG")
        lbl_t.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; border: none;")
        b_layout.addWidget(lbl_t)

        # UUID row
        uuid_row = QWidget()
        uuid_row.setStyleSheet("border: none;")
        ur_layout = QHBoxLayout(uuid_row)
        ur_layout.setContentsMargins(0, 0, 0, 0)
        lbl_uuid = QLabel(f"Mã Motherboard UUID máy này: {self.current_device_uuid}")
        lbl_uuid.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; color: #64B5F6;")
        ur_layout.addWidget(lbl_uuid)

        btn_copy = QPushButton("📋 Sao chép UUID")
        btn_copy.setFixedSize(120, 26)
        btn_copy.setStyleSheet("background-color: #444444; color: white; border-radius: 4px; font-size: 11px;")
        btn_copy.clicked.connect(self.copy_current_uuid)
        ur_layout.addWidget(btn_copy)
        ur_layout.addStretch()
        b_layout.addWidget(uuid_row)

        # Action form
        form_row = QWidget()
        form_row.setStyleSheet("border: none;")
        fr_layout = QHBoxLayout(form_row)
        fr_layout.setContentsMargins(0, 0, 0, 0)
        fr_layout.setSpacing(10)

        self.dev_branch_combo = QComboBox()
        self.dev_branch_combo.setFixedWidth(200)
        fr_layout.addWidget(self.dev_branch_combo)

        self.dev_name_entry = QLineEdit()
        self.dev_name_entry.setPlaceholderText("Tên máy (VD: Quầy Thu Ngân 1)")
        self.dev_name_entry.setFixedWidth(240)
        fr_layout.addWidget(self.dev_name_entry)

        btn_reg = QPushButton("➕ Cấp phép máy này")
        btn_reg.setFixedHeight(34)
        btn_reg.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px; padding: 0px 14px;")
        btn_reg.clicked.connect(self.handle_register_current_device)
        fr_layout.addWidget(btn_reg)

        btn_manual = QPushButton("➕ Thêm máy khác thủ công")
        btn_manual.setFixedHeight(34)
        btn_manual.setStyleSheet("background-color: #17A2B8; color: white; font-weight: bold; border-radius: 6px; padding: 0px 14px;")
        btn_manual.clicked.connect(self.open_add_custom_device_dialog)
        fr_layout.addWidget(btn_manual)

        fr_layout.addStretch()
        b_layout.addWidget(form_row)
        layout.addWidget(box)

        # Scroll list
        self.scroll_devices = QScrollArea()
        self.scroll_devices.setWidgetResizable(True)
        self.content_devices = QWidget()
        self.layout_devices = QVBoxLayout(self.content_devices)
        self.layout_devices.setSpacing(8)
        self.scroll_devices.setWidget(self.content_devices)
        layout.addWidget(self.scroll_devices)

        self.tab_widget.addTab(tab, "Khóa máy quầy (Hardware UUID)")

    def copy_current_uuid(self):
        QApplication.clipboard().setText(self.current_device_uuid)
        QMessageBox.information(self, "Đã sao chép", "Đã sao chép mã Motherboard UUID vào bộ nhớ tạm!")

    def load_devices_list(self):
        while self.layout_devices.count():
            item = self.layout_devices.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl_loading = QLabel("⏳ Đang tải danh sách máy quầy cấp phép...")
        lbl_loading.setStyleSheet("font-size: 13px; color: gray; padding: 30px;")
        lbl_loading.setAlignment(Qt.AlignCenter)
        self.layout_devices.addWidget(lbl_loading)

        def worker():
            b = self.refresh_branch_cache()
            d = self.supabase.get_allowed_devices()
            return b, d

        def on_done(data):
            branches, devices = data
            while self.layout_devices.count():
                item = self.layout_devices.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            b_names = list(self.branch_map.keys())
            self.dev_branch_combo.clear()
            self.dev_branch_combo.addItems(b_names)

            if not devices:
                lbl = QLabel("Chưa có thiết bị nào được cấp phép trong hệ thống.")
                lbl.setStyleSheet("font-size: 13px; color: gray; padding: 30px;")
                lbl.setAlignment(Qt.AlignCenter)
                self.layout_devices.addWidget(lbl)
                return

            for dev in devices:
                card = self._create_device_card(dev)
                self.layout_devices.addWidget(card)
            self.layout_devices.addStretch()

        self.worker = QtWorker(worker)
        self.worker.result_ready.connect(on_done)
        self.worker.start()

    def _create_device_card(self, dev):
        row = QFrame()
        row.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 8px; padding: 8px 15px;")
        r_layout = QHBoxLayout(row)

        b_name = dev.get("branches", {}).get("name", "Chưa gán") if dev.get("branches") else "Chưa gán"
        d_name = dev.get("device_name", "Thiết bị không tên")
        d_uuid = dev.get("device_uuid", "")
        is_active = dev.get("is_active", True)
        is_current = (d_uuid == self.current_device_uuid)

        left = QVBoxLayout()
        left.setSpacing(2)
        lbl_title = QLabel(f"🖥️ {d_name}  •  🏥 {b_name}")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF; border: none;")
        left.addWidget(lbl_title)

        status_txt = "🟢 Đang hoạt động" if is_active else "🔴 Đã tạm khóa"
        uuid_display = f"UUID: {d_uuid}" + ("  ★ [MÁY NÀY]" if is_current else "") + f"  •  {status_txt}"
        lbl_sub = QLabel(uuid_display)
        color = "#28A745" if is_current else "#888888"
        lbl_sub.setStyleSheet(f"font-family: Consolas, monospace; font-size: 11px; color: {color}; border: none;")
        left.addWidget(lbl_sub)
        r_layout.addLayout(left)

        r_layout.addStretch()

        btn_edit = QPushButton("✏️ Sửa")
        btn_edit.setFixedSize(70, 28)
        btn_edit.setStyleSheet("background-color: #1F6AA5; color: white; border-radius: 4px; font-weight: bold;")
        btn_edit.clicked.connect(lambda: self.open_edit_device_dialog(dev))
        r_layout.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Xóa")
        btn_del.setFixedSize(70, 28)
        btn_del.setStyleSheet("background-color: #DC3545; color: white; border-radius: 4px; font-weight: bold;")
        btn_del.clicked.connect(lambda: self.handle_delete_device(dev))
        r_layout.addWidget(btn_del)

        return row

    def handle_register_current_device(self):
        b_name = self.dev_branch_combo.currentText()
        branch_id = self.branch_map.get(b_name)
        dev_name = self.dev_name_entry.text().strip()

        if not branch_id or not dev_name:
            QMessageBox.warning(self, "Lưu ý", "Vui lòng chọn Chi nhánh và nhập Tên máy!")
            return

        res = self.supabase.register_device(branch_id, self.current_device_uuid, dev_name)
        if res.get("success"):
            QMessageBox.information(self, "Thành công", f"Đã cấp phép máy '{dev_name}' cho chi nhánh {b_name}!")
            self.dev_name_entry.clear()
            self.load_devices_list()
        else:
            QMessageBox.critical(self, "Lỗi", res.get("message", "Không thể cấp phép thiết bị."))

    def open_add_custom_device_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Thêm Máy Tính Thủ Công (Hardware UUID)")
        dlg.resize(450, 360)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        lbl = QLabel("➕ THÊM MÁY TÍNH QUẦY KHÁC")
        lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(lbl)

        layout.addWidget(QLabel("Chọn Chi nhánh phân công:"))
        b_combo = QComboBox()
        b_names = list(self.branch_map.keys())
        if not b_names:
            QMessageBox.warning(dlg, "Lưu ý", "Chưa có chi nhánh nào! Vui lòng tạo chi nhánh trước.")
            dlg.reject()
            return
        b_combo.addItems(b_names)
        layout.addWidget(b_combo)

        layout.addWidget(QLabel("Tên máy nhận diện:"))
        name_ent = QLineEdit()
        name_ent.setPlaceholderText("VD: Máy Quầy Thu Ngân 2")
        layout.addWidget(name_ent)

        layout.addWidget(QLabel("Motherboard UUID của máy quầy:"))
        uuid_ent = QLineEdit()
        uuid_ent.setPlaceholderText("VD: 45508223-B414-8545-88EF-EBCBD71CD861")
        layout.addWidget(uuid_ent)

        def save():
            b_id = self.branch_map.get(b_combo.currentText())
            d_name = name_ent.text().strip()
            d_uuid = uuid_ent.text().strip()
            if not b_id or not d_name or not d_uuid:
                QMessageBox.warning(dlg, "Lưu ý", "Vui lòng nhập đầy đủ Chi nhánh, Tên máy và mã UUID!")
                return
            res = self.supabase.register_device(b_id, d_uuid, d_name)
            if res.get("success"):
                QMessageBox.information(dlg, "Thành công", f"Đã đăng ký máy '{d_name}' vào hệ thống!")
                dlg.accept()
                self.load_devices_list()
            else:
                QMessageBox.critical(dlg, "Thông báo", res.get("message", "Không thể lưu thiết bị."))

        btn_save = QPushButton("💾 LƯU MÁY TÍNH")
        btn_save.setFixedHeight(38)
        btn_save.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px;")
        btn_save.clicked.connect(save)
        layout.addWidget(btn_save)

        dlg.exec()

    def open_edit_device_dialog(self, dev):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Sửa Thiết Bị - {dev.get('device_name')}")
        dlg.resize(450, 360)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        lbl = QLabel(f"✏️ CHỈNH SỬA MÁY: {dev.get('device_name')}")
        lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(lbl)

        layout.addWidget(QLabel("Chi nhánh:"))
        b_combo = QComboBox()
        b_names = list(self.branch_map.keys())
        b_combo.addItems(b_names)
        cur_b_name = dev.get("branches", {}).get("name") if dev.get("branches") else None
        if cur_b_name in b_names:
            b_combo.setCurrentText(cur_b_name)
        layout.addWidget(b_combo)

        layout.addWidget(QLabel("Tên máy:"))
        name_ent = QLineEdit()
        name_ent.setText(dev.get("device_name", ""))
        layout.addWidget(name_ent)

        layout.addWidget(QLabel("Trạng thái:"))
        st_combo = QComboBox()
        st_combo.addItem("🟢 Cho phép hoạt động", True)
        st_combo.addItem("🔴 Tạm khóa thiết bị", False)
        st_combo.setCurrentIndex(0 if dev.get("is_active", True) else 1)
        layout.addWidget(st_combo)

        def save():
            b_id = self.branch_map.get(b_combo.currentText())
            d_name = name_ent.text().strip()
            is_act = st_combo.currentData()
            if not b_id or not d_name:
                QMessageBox.warning(dlg, "Lưu ý", "Vui lòng nhập Tên máy!")
                return
            res = self.supabase.update_device(dev.get("id"), b_id, d_name, is_act)
            if res.get("success"):
                QMessageBox.information(dlg, "Thành công", "Đã cập nhật thông tin máy tính!")
                dlg.accept()
                self.load_devices_list()
            else:
                QMessageBox.critical(dlg, "Lỗi", res.get("message", "Không thể cập nhật thiết bị."))

        btn_save = QPushButton("💾 LƯU THAY ĐỔI")
        btn_save.setFixedHeight(38)
        btn_save.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px;")
        btn_save.clicked.connect(save)
        layout.addWidget(btn_save)

        dlg.exec()

    def handle_delete_device(self, dev):
        d_name = dev.get("device_name")
        reply = QMessageBox.question(
            self, "Xác nhận xóa", f"Bạn có chắc muốn xóa quyền thiết bị '{d_name}' khỏi hệ thống?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            res = self.supabase.delete_device(dev.get("id"))
            if res.get("success"):
                QMessageBox.information(self, "Thành công", f"Đã xóa thiết bị '{d_name}'!")
                self.load_devices_list()
            else:
                QMessageBox.critical(self, "Lỗi", res.get("message", "Không thể xóa thiết bị."))

    # =========================================================================
    # TAB 2: QUẢN LÝ CHI NHÁNH
    # =========================================================================
    def setup_branches_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        box = QFrame()
        box.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px; padding: 15px;")
        b_layout = QVBoxLayout(box)
        b_layout.setSpacing(10)

        lbl = QLabel("🏥 THÊM CHI NHÁNH NHÀ THUỐC MỚI")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; border: none;")
        b_layout.addWidget(lbl)

        form_row = QWidget()
        form_row.setStyleSheet("border: none;")
        fr_layout = QHBoxLayout(form_row)
        fr_layout.setContentsMargins(0, 0, 0, 0)
        fr_layout.setSpacing(10)

        self.b_name_entry = QLineEdit()
        self.b_name_entry.setPlaceholderText("Tên chi nhánh (VD: Nhà thuốc CS2 - Bình Thạnh)")
        self.b_name_entry.setFixedWidth(280)
        fr_layout.addWidget(self.b_name_entry)

        self.b_addr_entry = QLineEdit()
        self.b_addr_entry.setPlaceholderText("Địa chỉ chi nhánh")
        self.b_addr_entry.setFixedWidth(320)
        fr_layout.addWidget(self.b_addr_entry)

        btn_add = QPushButton("➕ Tạo chi nhánh")
        btn_add.setFixedHeight(34)
        btn_add.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px; padding: 0px 14px;")
        btn_add.clicked.connect(self.handle_add_branch)
        fr_layout.addWidget(btn_add)

        fr_layout.addStretch()
        b_layout.addWidget(form_row)
        layout.addWidget(box)

        self.scroll_branches = QScrollArea()
        self.scroll_branches.setWidgetResizable(True)
        self.content_branches = QWidget()
        self.layout_branches = QVBoxLayout(self.content_branches)
        self.layout_branches.setSpacing(8)
        self.scroll_branches.setWidget(self.content_branches)
        layout.addWidget(self.scroll_branches)

        self.tab_widget.addTab(tab, "Chi nhánh")

    def load_branches_list(self):
        while self.layout_branches.count():
            item = self.layout_branches.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl_loading = QLabel("⏳ Đang tải danh sách chi nhánh...")
        lbl_loading.setStyleSheet("font-size: 13px; color: gray; padding: 30px;")
        lbl_loading.setAlignment(Qt.AlignCenter)
        self.layout_branches.addWidget(lbl_loading)

        def worker():
            branches = self.refresh_branch_cache()
            sm_map = {}
            if branches:
                for b in branches:
                    b_id = b.get("id")
                    sm = self.supabase.get_branch_storemanager(b_id)
                    sm_map[b_id] = sm
            return branches, sm_map

        def on_done(data):
            branches, sm_map = data
            while self.layout_branches.count():
                item = self.layout_branches.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not branches:
                lbl = QLabel("Chưa có chi nhánh nào trong hệ thống.")
                lbl.setStyleSheet("font-size: 13px; color: gray; padding: 30px;")
                lbl.setAlignment(Qt.AlignCenter)
                self.layout_branches.addWidget(lbl)
                return

            for b in branches:
                card = self._create_branch_card(b, sm_map.get(b.get("id")))
                self.layout_branches.addWidget(card)
            self.layout_branches.addStretch()

        self.worker = QtWorker(worker)
        self.worker.result_ready.connect(on_done)
        self.worker.start()

    def _create_branch_card(self, b, sm):
        row = QFrame()
        row.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 8px; padding: 8px 15px;")
        r_layout = QHBoxLayout(row)

        name = b.get("name", "")
        addr = b.get("address", "") or "Chưa có địa chỉ"
        sm_txt = f"👑 Quản lý: {sm.get('full_name')}" if sm else "⚠️ Chưa có Quản lý chi nhánh"

        left = QVBoxLayout()
        left.setSpacing(2)
        lbl_title = QLabel(f"🏥 {name}")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF; border: none;")
        left.addWidget(lbl_title)

        lbl_sub = QLabel(f"📍 {addr}   •   {sm_txt}")
        col = "#9C27B0" if sm else "gray"
        lbl_sub.setStyleSheet(f"font-size: 11px; color: {col}; border: none;")
        left.addWidget(lbl_sub)
        r_layout.addLayout(left)

        r_layout.addStretch()

        btn_edit = QPushButton("✏️ Sửa")
        btn_edit.setFixedSize(70, 28)
        btn_edit.setStyleSheet("background-color: #1F6AA5; color: white; border-radius: 4px; font-weight: bold;")
        btn_edit.clicked.connect(lambda: self.open_edit_branch_dialog(b))
        r_layout.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Xóa")
        btn_del.setFixedSize(70, 28)
        btn_del.setStyleSheet("background-color: #DC3545; color: white; border-radius: 4px; font-weight: bold;")
        btn_del.clicked.connect(lambda: self.handle_delete_branch(b))
        r_layout.addWidget(btn_del)

        return row

    def handle_add_branch(self):
        name = self.b_name_entry.text().strip()
        addr = self.b_addr_entry.text().strip()
        if not name:
            QMessageBox.warning(self, "Lưu ý", "Tên chi nhánh không được để trống!")
            return

        res = self.supabase.create_branch(name, addr)
        if res.get("success"):
            QMessageBox.information(self, "Thành công", f"Đã tạo chi nhánh '{name}'!")
            self.b_name_entry.clear()
            self.b_addr_entry.clear()
            self.load_branches_list()
            self.load_devices_list()
        else:
            QMessageBox.critical(self, "Lỗi", res.get("message", "Không thể tạo chi nhánh."))

    def open_edit_branch_dialog(self, br):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Sửa Chi Nhánh - {br.get('name')}")
        dlg.resize(450, 280)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        lbl = QLabel(f"✏️ SỬA CHI NHÁNH: {br.get('name')}")
        lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(lbl)

        layout.addWidget(QLabel("Tên chi nhánh:"))
        name_ent = QLineEdit()
        name_ent.setText(br.get("name", ""))
        layout.addWidget(name_ent)

        layout.addWidget(QLabel("Địa chỉ:"))
        addr_ent = QLineEdit()
        addr_ent.setText(br.get("address", "") or "")
        layout.addWidget(addr_ent)

        def save():
            name = name_ent.text().strip()
            addr = addr_ent.text().strip()
            if not name:
                QMessageBox.warning(dlg, "Lưu ý", "Tên chi nhánh không được để trống!")
                return
            res = self.supabase.update_branch(br.get("id"), name, addr)
            if res.get("success"):
                QMessageBox.information(dlg, "Thành công", "Đã cập nhật chi nhánh!")
                dlg.accept()
                self.load_branches_list()
                self.load_devices_list()
            else:
                QMessageBox.critical(dlg, "Lỗi", res.get("message", "Không thể cập nhật chi nhánh."))

        btn_save = QPushButton("💾 LƯU THAY ĐỔI")
        btn_save.setFixedHeight(38)
        btn_save.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px;")
        btn_save.clicked.connect(save)
        layout.addWidget(btn_save)

        dlg.exec()

    def handle_delete_branch(self, br):
        name = br.get("name")
        reply = QMessageBox.question(
            self, "Xác nhận xóa", f"Bạn có chắc muốn xóa chi nhánh '{name}'?\nLưu ý: Nếu có thiết bị, ca làm hoặc nhân viên thuộc chi nhánh thì cần chuyển trước.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            res = self.supabase.delete_branch(br.get("id"))
            if res.get("success"):
                QMessageBox.information(self, "Thành công", f"Đã xóa chi nhánh '{name}'!")
                self.load_branches_list()
                self.load_devices_list()
            else:
                QMessageBox.critical(self, "Lỗi", res.get("message", "Không thể xóa chi nhánh."))

    # =========================================================================
    # TAB 3: QUẢN LÝ CA LÀM VIỆC (SHIFTS)
    # =========================================================================
    def setup_shifts_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        box = QFrame()
        box.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px; padding: 15px;")
        b_layout = QVBoxLayout(box)
        b_layout.setSpacing(10)

        lbl = QLabel("⏰ TẠO CA LÀM VIỆC CHO CHI NHÁNH")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; border: none;")
        b_layout.addWidget(lbl)

        form_row = QWidget()
        form_row.setStyleSheet("border: none;")
        fr_layout = QHBoxLayout(form_row)
        fr_layout.setContentsMargins(0, 0, 0, 0)
        fr_layout.setSpacing(10)

        self.shift_branch_combo = QComboBox()
        self.shift_branch_combo.setFixedWidth(190)
        fr_layout.addWidget(self.shift_branch_combo)

        self.shift_name_entry = QLineEdit()
        self.shift_name_entry.setPlaceholderText("Tên ca (VD: Ca Sáng)")
        self.shift_name_entry.setFixedWidth(160)
        fr_layout.addWidget(self.shift_name_entry)

        self.shift_start_entry = QLineEdit()
        self.shift_start_entry.setPlaceholderText("08:00:00")
        self.shift_start_entry.setFixedWidth(95)
        fr_layout.addWidget(self.shift_start_entry)

        fr_layout.addWidget(QLabel("đến"))

        self.shift_end_entry = QLineEdit()
        self.shift_end_entry.setPlaceholderText("16:00:00")
        self.shift_end_entry.setFixedWidth(95)
        fr_layout.addWidget(self.shift_end_entry)

        btn_add = QPushButton("➕ Tạo Ca")
        btn_add.setFixedHeight(34)
        btn_add.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px; padding: 0px 14px;")
        btn_add.clicked.connect(self.handle_add_shift)
        fr_layout.addWidget(btn_add)

        fr_layout.addStretch()
        b_layout.addWidget(form_row)
        layout.addWidget(box)

        self.scroll_shifts = QScrollArea()
        self.scroll_shifts.setWidgetResizable(True)
        self.content_shifts = QWidget()
        self.layout_shifts = QVBoxLayout(self.content_shifts)
        self.layout_shifts.setSpacing(8)
        self.scroll_shifts.setWidget(self.content_shifts)
        layout.addWidget(self.scroll_shifts)

        self.tab_widget.addTab(tab, "Ca làm việc")

    def load_shifts_list(self):
        while self.layout_shifts.count():
            item = self.layout_shifts.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl_loading = QLabel("⏳ Đang tải danh sách ca làm việc...")
        lbl_loading.setStyleSheet("font-size: 13px; color: gray; padding: 30px;")
        lbl_loading.setAlignment(Qt.AlignCenter)
        self.layout_shifts.addWidget(lbl_loading)

        def worker():
            branches = self.refresh_branch_cache()
            shifts = self.supabase.get_shifts(force_refresh=True)
            return branches, shifts

        def on_done(data):
            branches, shifts = data
            while self.layout_shifts.count():
                item = self.layout_shifts.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            b_names = list(self.branch_map.keys())
            self.shift_branch_combo.clear()
            self.shift_branch_combo.addItems(b_names)

            if not shifts:
                lbl = QLabel("Chưa có ca làm việc nào.")
                lbl.setStyleSheet("font-size: 13px; color: gray; padding: 30px;")
                lbl.setAlignment(Qt.AlignCenter)
                self.layout_shifts.addWidget(lbl)
                return

            for s in shifts:
                card = self._create_shift_card(s)
                self.layout_shifts.addWidget(card)
            self.layout_shifts.addStretch()

        self.worker = QtWorker(worker)
        self.worker.result_ready.connect(on_done)
        self.worker.start()

    def _create_shift_card(self, s):
        row = QFrame()
        row.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 8px; padding: 8px 15px;")
        r_layout = QHBoxLayout(row)

        name = s.get("name", "")
        st = s.get("start_time", "")[:5]
        et = s.get("end_time", "")[:5]
        b_name = s.get("branches", {}).get("name", "Chưa gán") if s.get("branches") else "Tất cả chi nhánh"

        left = QVBoxLayout()
        left.setSpacing(2)
        lbl_title = QLabel(f"⏰ {name}   ({st} - {et})")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF; border: none;")
        left.addWidget(lbl_title)

        lbl_sub = QLabel(f"🏥 Chi nhánh: {b_name}")
        lbl_sub.setStyleSheet("font-size: 11px; color: gray; border: none;")
        left.addWidget(lbl_sub)
        r_layout.addLayout(left)

        r_layout.addStretch()

        btn_edit = QPushButton("✏️ Sửa")
        btn_edit.setFixedSize(70, 28)
        btn_edit.setStyleSheet("background-color: #1F6AA5; color: white; border-radius: 4px; font-weight: bold;")
        btn_edit.clicked.connect(lambda: self.open_edit_shift_dialog(s))
        r_layout.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Xóa")
        btn_del.setFixedSize(70, 28)
        btn_del.setStyleSheet("background-color: #DC3545; color: white; border-radius: 4px; font-weight: bold;")
        btn_del.clicked.connect(lambda: self.handle_delete_shift(s))
        r_layout.addWidget(btn_del)

        return row

    def handle_add_shift(self):
        b_name = self.shift_branch_combo.currentText()
        b_id = self.branch_map.get(b_name)
        s_name = self.shift_name_entry.text().strip()
        st = self.shift_start_entry.text().strip()
        et = self.shift_end_entry.text().strip()

        if not b_id or not s_name or not st or not et:
            QMessageBox.warning(self, "Lưu ý", "Vui lòng nhập đầy đủ Chi nhánh, Tên ca, Giờ bắt đầu và Giờ kết thúc!")
            return

        res = self.supabase.create_shift(b_id, s_name, st, et)
        if res.get("success"):
            QMessageBox.information(self, "Thành công", f"Đã tạo ca làm việc '{s_name}'!")
            self.shift_name_entry.clear()
            self.shift_start_entry.clear()
            self.shift_end_entry.clear()
            self.load_shifts_list()
        else:
            QMessageBox.critical(self, "Lỗi", res.get("message", "Không thể tạo ca làm việc."))

    def open_edit_shift_dialog(self, shift):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Sửa Ca Làm - {shift.get('name')}")
        dlg.resize(450, 360)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        lbl = QLabel(f"✏️ CHỈNH SỬA CA LÀM: {shift.get('name')}")
        lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(lbl)

        layout.addWidget(QLabel("Chi nhánh:"))
        b_combo = QComboBox()
        b_names = list(self.branch_map.keys())
        b_combo.addItems(b_names)
        cur_b_name = shift.get("branches", {}).get("name") if shift.get("branches") else None
        if cur_b_name in b_names:
            b_combo.setCurrentText(cur_b_name)
        layout.addWidget(b_combo)

        layout.addWidget(QLabel("Tên ca làm:"))
        name_ent = QLineEdit()
        name_ent.setText(shift.get("name", ""))
        layout.addWidget(name_ent)

        layout.addWidget(QLabel("Giờ bắt đầu (HH:MM:SS):"))
        st_ent = QLineEdit()
        st_ent.setText(shift.get("start_time", ""))
        layout.addWidget(st_ent)

        layout.addWidget(QLabel("Giờ kết thúc (HH:MM:SS):"))
        et_ent = QLineEdit()
        et_ent.setText(shift.get("end_time", ""))
        layout.addWidget(et_ent)

        def save():
            b_id = self.branch_map.get(b_combo.currentText())
            s_name = name_ent.text().strip()
            st = st_ent.text().strip()
            et = et_ent.text().strip()
            if not s_name or not st or not et:
                QMessageBox.warning(dlg, "Lưu ý", "Vui lòng nhập đầy đủ Tên ca và Giờ!")
                return
            res = self.supabase.update_shift(shift.get("id"), b_id, s_name, st, et)
            if res.get("success"):
                QMessageBox.information(dlg, "Thành công", "Đã cập nhật ca làm việc!")
                dlg.accept()
                self.load_shifts_list()
            else:
                QMessageBox.critical(dlg, "Lỗi", res.get("message", "Không thể cập nhật ca làm việc."))

        btn_save = QPushButton("💾 LƯU THAY ĐỔI")
        btn_save.setFixedHeight(38)
        btn_save.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px;")
        btn_save.clicked.connect(save)
        layout.addWidget(btn_save)

        dlg.exec()

    def handle_delete_shift(self, shift):
        name = shift.get("name")
        reply = QMessageBox.question(
            self, "Xác nhận xóa", f"Bạn có chắc muốn xóa ca làm việc '{name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            res = self.supabase.delete_shift(shift.get("id"))
            if res.get("success"):
                QMessageBox.information(self, "Thành công", f"Đã xóa ca '{name}'!")
                self.load_shifts_list()
            else:
                QMessageBox.critical(self, "Lỗi", res.get("message", "Không thể xóa ca làm việc."))

    # =========================================================================
    # TAB 4: NHÂN SỰ & PHÂN QUYỀN
    # =========================================================================
    def setup_users_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px; padding: 10px 15px;")
        tb_layout = QHBoxLayout(top_bar)

        self.users_count_lbl = QLabel("👥 Quản lý nhân viên toàn chuỗi (Quy tắc: 1 Admin tối cao, mỗi chi nhánh tối đa 1 Quản lý)")
        self.users_count_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #CCCCCC; border: none;")
        tb_layout.addWidget(self.users_count_lbl)

        tb_layout.addStretch()

        btn_create = QPushButton("➕ TẠO TÀI KHOẢN NHÂN VIÊN MỚI")
        btn_create.setFixedHeight(36)
        btn_create.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px; padding: 0px 14px;")
        btn_create.clicked.connect(self.open_create_user_dialog)
        tb_layout.addWidget(btn_create)

        layout.addWidget(top_bar)

        self.scroll_users = QScrollArea()
        self.scroll_users.setWidgetResizable(True)
        self.content_users = QWidget()
        self.layout_users = QVBoxLayout(self.content_users)
        self.layout_users.setSpacing(8)
        self.scroll_users.setWidget(self.content_users)
        layout.addWidget(self.scroll_users)

        self.tab_widget.addTab(tab, "Nhân sự & Phân quyền")

    def load_users_list(self):
        while self.layout_users.count():
            item = self.layout_users.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl_loading = QLabel("⏳ Đang tải danh sách nhân sự...")
        lbl_loading.setStyleSheet("font-size: 13px; color: gray; padding: 30px;")
        lbl_loading.setAlignment(Qt.AlignCenter)
        self.layout_users.addWidget(lbl_loading)

        def worker():
            self.refresh_branch_cache()
            return self.supabase.get_staff_list(force_refresh=True)

        def on_done(users):
            while self.layout_users.count():
                item = self.layout_users.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not users:
                lbl = QLabel("Chưa có nhân viên nào trong cơ sở dữ liệu.")
                lbl.setStyleSheet("font-size: 13px; color: gray; padding: 30px;")
                lbl.setAlignment(Qt.AlignCenter)
                self.layout_users.addWidget(lbl)
                return

            self.users_count_lbl.setText(f"👥 Tổng cộng: {len(users)} nhân sự  •  Hệ thống: Duy nhất 1 Admin tối cao, mỗi CN tối đa 1 Quản lý")

            for u in users:
                card = self._create_user_card(u)
                self.layout_users.addWidget(card)
            self.layout_users.addStretch()

        self.worker = QtWorker(worker)
        self.worker.result_ready.connect(on_done)
        self.worker.start()

    def _create_user_card(self, u):
        row = QFrame()
        row.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 8px; padding: 8px 15px;")
        r_layout = QHBoxLayout(row)

        name = u.get("full_name", "")
        role = u.get("role", "staff").lower()
        b_name = u.get("branches", {}).get("name", "Chưa gán chi nhánh") if u.get("branches") else "Chưa gán chi nhánh"
        phone = u.get("phone", "") or "Chưa có SĐT"
        active = u.get("is_active", True)
        is_admin = (role == "admin")

        if is_admin:
            role_label = "[👑 ADMIN CHỦ CHUỖI]"
            role_color = "#DC3545"
        elif role == "storemanager":
            role_label = "[⭐ CỬA HÀNG TRƯỞNG]"
            role_color = "#9C27B0"
        else:
            role_label = "[💊 DƯỢC SĨ QUẦY]"
            role_color = "#64B5F6"

        status_str = "🟢 Hoạt động" if active else "🔴 Đã tạm khóa"

        left = QVBoxLayout()
        left.setSpacing(2)
        lbl_title = QLabel(f"👤 {name}   {role_label}")
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {role_color}; border: none;")
        left.addWidget(lbl_title)

        lbl_sub = QLabel(f"🏥 {b_name}   •   📞 {phone}   •   {status_str}")
        lbl_sub.setStyleSheet("font-size: 11px; color: gray; border: none;")
        left.addWidget(lbl_sub)
        r_layout.addLayout(left)

        r_layout.addStretch()

        if is_admin:
            lbl_adm = QLabel("🛡️ Tài khoản gốc (Bảo vệ)")
            lbl_adm.setStyleSheet("font-size: 12px; font-weight: bold; color: #DC3545; border: none;")
            r_layout.addWidget(lbl_adm)
        else:
            btn_edit = QPushButton("✏️ Sửa & Quyền")
            btn_edit.setFixedSize(110, 28)
            btn_edit.setStyleSheet("background-color: #1F6AA5; color: white; border-radius: 4px; font-weight: bold;")
            btn_edit.clicked.connect(lambda: self.open_edit_user_dialog(u))
            r_layout.addWidget(btn_edit)

            btn_del = QPushButton("🗑️ Xóa")
            btn_del.setFixedSize(70, 28)
            btn_del.setStyleSheet("background-color: #DC3545; color: white; border-radius: 4px; font-weight: bold;")
            btn_del.clicked.connect(lambda: self.handle_delete_user(u))
            r_layout.addWidget(btn_del)

        return row

    def open_create_user_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Tạo Tài Khoản Nhân Viên Mới")
        dlg.resize(480, 500)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        lbl = QLabel("➕ TẠO TÀI KHOẢN NHÂN VIÊN MỚI")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(lbl)

        layout.addWidget(QLabel("Họ và tên nhân viên:"))
        name_ent = QLineEdit()
        name_ent.setPlaceholderText("VD: Nguyễn Văn A")
        layout.addWidget(name_ent)

        layout.addWidget(QLabel("Tên đăng nhập hoặc Email:"))
        email_ent = QLineEdit()
        email_ent.setPlaceholderText("VD: duocsi1 (hoặc duocsi1@nhathuoc.com)")
        layout.addWidget(email_ent)

        layout.addWidget(QLabel("Mật khẩu khởi tạo:"))
        pass_ent = QLineEdit()
        pass_ent.setEchoMode(QLineEdit.Password)
        pass_ent.setText("123456")
        layout.addWidget(pass_ent)

        layout.addWidget(QLabel("Số điện thoại liên hệ:"))
        phone_ent = QLineEdit()
        phone_ent.setPlaceholderText("VD: 0912345678")
        layout.addWidget(phone_ent)

        layout.addWidget(QLabel("Chi nhánh phân công:"))
        b_combo = QComboBox()
        b_names = list(self.branch_map.keys())
        if not b_names:
            QMessageBox.warning(dlg, "Lưu ý", "Chưa có chi nhánh nào! Vui lòng tạo chi nhánh trước.")
            dlg.reject()
            return
        b_combo.addItems(b_names)
        layout.addWidget(b_combo)

        layout.addWidget(QLabel("Vai trò trong hệ thống:"))
        role_combo = QComboBox()
        role_combo.addItem("💊 Dược sĩ quầy (staff)", "staff")
        role_combo.addItem("⭐ Cửa hàng trưởng (storemanager)", "storemanager")
        layout.addWidget(role_combo)

        def save():
            full_name = name_ent.text().strip()
            raw_email = email_ent.text().strip()
            password = pass_ent.text().strip()
            phone = phone_ent.text().strip()
            chosen_b = b_combo.currentText()
            branch_id = self.branch_map.get(chosen_b)
            role = role_combo.currentData()

            if not full_name or not raw_email or not password:
                QMessageBox.warning(dlg, "Lưu ý", "Vui lòng nhập Họ tên, Tên đăng nhập và Mật khẩu!")
                return

            if len(password) < 6:
                QMessageBox.warning(dlg, "Lưu ý", "Mật khẩu phải có độ dài tối thiểu 6 ký tự!")
                return

            email = raw_email if "@" in raw_email else f"{raw_email}@nhathuoc.com"

            if role == "storemanager":
                existing_sm = self.supabase.get_branch_storemanager(branch_id)
                if existing_sm:
                    QMessageBox.critical(
                        dlg, "Ràng buộc Cửa hàng trưởng",
                        f"Chi nhánh '{chosen_b}' hiện ĐÃ CÓ Cửa hàng trưởng là '{existing_sm.get('full_name')}'.\n\nMỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý!"
                    )
                    return

            res = self.supabase.create_user(email, password, full_name, role, branch_id, phone)
            if res.get("success"):
                QMessageBox.information(dlg, "Thành công", f"Đã tạo tài khoản cho nhân viên {full_name}!\n\nTài khoản: {email}\nMật khẩu: {password}")
                dlg.accept()
                self.load_users_list()
            else:
                QMessageBox.critical(dlg, "Lỗi", res.get("message", "Không thể tạo tài khoản nhân viên."))

        btn_save = QPushButton("💾 TẠO TÀI KHOẢN NGAY")
        btn_save.setFixedHeight(40)
        btn_save.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px;")
        btn_save.clicked.connect(save)
        layout.addWidget(btn_save)

        dlg.exec()

    def open_edit_user_dialog(self, user):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Chỉnh Sửa - {user.get('full_name')}")
        dlg.resize(480, 480)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        lbl = QLabel(f"✏️ SỬA NHÂN VIÊN: {user.get('full_name')}")
        lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(lbl)

        layout.addWidget(QLabel("Họ và tên:"))
        name_ent = QLineEdit()
        name_ent.setText(user.get("full_name", ""))
        layout.addWidget(name_ent)

        layout.addWidget(QLabel("Số điện thoại:"))
        phone_ent = QLineEdit()
        phone_ent.setText(user.get("phone", "") or "")
        layout.addWidget(phone_ent)

        layout.addWidget(QLabel("Chi nhánh:"))
        b_combo = QComboBox()
        b_names = list(self.branch_map.keys())
        b_combo.addItems(b_names)
        cur_b_name = user.get("branches", {}).get("name") if user.get("branches") else None
        if cur_b_name in b_names:
            b_combo.setCurrentText(cur_b_name)
        layout.addWidget(b_combo)

        layout.addWidget(QLabel("Vai trò:"))
        role_combo = QComboBox()
        role_combo.addItem("💊 Dược sĩ quầy (staff)", "staff")
        role_combo.addItem("⭐ Cửa hàng trưởng (storemanager)", "storemanager")
        cur_role = user.get("role", "staff")
        role_combo.setCurrentIndex(1 if cur_role == "storemanager" else 0)
        layout.addWidget(role_combo)

        layout.addWidget(QLabel("Trạng thái:"))
        st_combo = QComboBox()
        st_combo.addItem("🟢 Đang hoạt động", True)
        st_combo.addItem("🔴 Tạm khóa tài khoản", False)
        st_combo.setCurrentIndex(0 if user.get("is_active", True) else 1)
        layout.addWidget(st_combo)

        def save():
            full_name = name_ent.text().strip()
            phone = phone_ent.text().strip()
            chosen_b = b_combo.currentText()
            branch_id = self.branch_map.get(chosen_b)
            role = role_combo.currentData()
            is_active = st_combo.currentData()

            if not full_name:
                QMessageBox.warning(dlg, "Lưu ý", "Vui lòng nhập Họ tên nhân viên!")
                return

            if role == "storemanager" and (cur_role != "storemanager" or user.get("branch_id") != branch_id):
                existing_sm = self.supabase.get_branch_storemanager(branch_id)
                if existing_sm and existing_sm.get("id") != user.get("id"):
                    QMessageBox.critical(
                        dlg, "Ràng buộc Cửa hàng trưởng",
                        f"Chi nhánh '{chosen_b}' đã có Quản lý là '{existing_sm.get('full_name')}'.\nMỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý!"
                    )
                    return

            res = self.supabase.update_user(user.get("id"), full_name, role, branch_id, phone, is_active)
            if res.get("success"):
                QMessageBox.information(dlg, "Thành công", "Đã cập nhật thông tin nhân viên!")
                dlg.accept()
                self.load_users_list()
            else:
                QMessageBox.critical(dlg, "Lỗi", res.get("message", "Không thể cập nhật nhân viên."))

        btn_save = QPushButton("💾 LƯU THAY ĐỔI")
        btn_save.setFixedHeight(40)
        btn_save.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px;")
        btn_save.clicked.connect(save)
        layout.addWidget(btn_save)

        dlg.exec()

    def handle_delete_user(self, user):
        name = user.get("full_name")
        reply = QMessageBox.question(
            self, "Xác nhận xóa", f"Bạn có chắc muốn xóa nhân viên '{name}' khỏi hệ thống?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            res = self.supabase.delete_user(user.get("id"))
            if res.get("success"):
                QMessageBox.information(self, "Thành công", f"Đã xóa nhân viên '{name}'!")
                self.load_users_list()
            else:
                QMessageBox.critical(self, "Lỗi", res.get("message", "Không thể xóa nhân viên."))
