from datetime import time
from PySide6.QtWidgets import QHBoxLayout, QComboBox, QMessageBox, QApplication
from core.hardware import get_hardware_uuid
from core.domain import ROLES
from views_qt.common import Page, TableModel, table_for, button, label, FormDialog


class SettingsView(Page):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent, current_profile)
        self.data = {}
        self.ready = False
        self.current_device_uuid = ""
        self.heading("Quản trị hệ thống", "Quản lý danh mục, thiết bị và quyền truy cập của nhân viên.")
        toolbar = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.setMinimumWidth(180)
        for caption, value in [
            ("Chi nhánh", "branches"),
            ("Ca làm việc", "shifts"),
            ("Máy quầy", "devices"),
            ("Nhân sự", "staff"),
        ]:
            self.kind.addItem(caption, value)
        toolbar.addWidget(self.kind)
        toolbar.addWidget(button("Làm mới", self.refresh))
        toolbar.addStretch()
        self.add_btn = button("Thêm mới", self.add, True)
        self.edit_btn = button("Chỉnh sửa", self.edit)
        self.delete_btn = button("Xóa", self.delete)
        for widget in [self.add_btn, self.edit_btn, self.delete_btn]:
            toolbar.addWidget(widget)
            widget.setEnabled(False)
        self.root.addLayout(toolbar)
        self.device_label = label("Đang xác định máy quầy…")
        self.root.addWidget(self.device_label)
        self.model = TableModel([], self)
        self.table = table_for(self.model)
        self.root.addWidget(self.table, 1)
        self.root.addWidget(self.status)
        copy = button("Sao chép mã máy này", self.copy_uuid)
        self.root.addWidget(copy)
        self.kind.currentIndexChanged.connect(self.render)
        self.table.selectionModel().selectionChanged.connect(self.selection_changed)
        self.refresh()

    def copy_uuid(self):
        if self.current_device_uuid:
            QApplication.clipboard().setText(self.current_device_uuid)
            self.status.setText("Đã sao chép mã máy.")

    def on_show(self):
        if self.ready:
            self.refresh()

    def refresh(self):
        if self.current_profile.get("role") != "admin":
            self.error("Chỉ chủ chuỗi có quyền quản trị hệ thống.")
            return
        self.ready = False
        self.model.replace([])
        self.add_btn.setEnabled(False)
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status.setText("Đang tải danh mục…")

        def fetch():
            return {
                "branches": self.supabase.get_branches(True),
                "shifts": self.supabase.get_shifts(force_refresh=True),
                "devices": self.supabase.get_allowed_devices(),
                "staff": self.supabase.get_staff_list(force_refresh=True),
                "identity": get_hardware_uuid(),
            }

        def done(data):
            self.data = data
            self.ready = True
            self.current_device_uuid = data["identity"]
            self.device_label.setText(f"Mã máy hiện tại: {self.current_device_uuid}")
            self.add_btn.setEnabled(True)
            self.render()

        self.tasks.submit("metadata", fetch, done, self.error)

    def selection_changed(self, *_):
        record = self.selected(self.table)
        protected = bool(record) and self.kind.currentData() == "staff" and record.get("role") == "admin"
        self.edit_btn.setEnabled(self.ready and bool(record) and not protected)
        self.delete_btn.setEnabled(self.ready and bool(record) and not protected)

    def render(self, *_):
        kind = self.kind.currentData()

        def branch_name(record):
            return (record.get("branches") or {}).get("name", "Chưa phân chi nhánh")

        columns = {
            "branches": [("Chi nhánh", lambda r: r.get("name")), ("Địa chỉ", lambda r: r.get("address"))],
            "shifts": [
                ("Tên ca", lambda r: r.get("name")),
                ("Chi nhánh", branch_name),
                ("Bắt đầu", lambda r: r.get("start_time")),
                ("Kết thúc", lambda r: r.get("end_time")),
            ],
            "devices": [
                ("Tên máy", lambda r: r.get("device_name")),
                ("Chi nhánh", branch_name),
                ("Mã máy", lambda r: r.get("device_uuid")),
                ("Trạng thái", lambda r: "Hoạt động" if r.get("is_active") else "Đã khóa"),
            ],
            "staff": [
                ("Họ tên", lambda r: r.get("full_name")),
                ("Chi nhánh", branch_name),
                ("Vai trò", lambda r: ROLES.get(r.get("role"), "Không rõ")),
                ("Điện thoại", lambda r: r.get("phone")),
                ("Trạng thái", lambda r: "Hoạt động" if r.get("is_active") else "Đã khóa"),
            ],
        }
        self.model.beginResetModel()
        self.model.columns = columns[kind]
        self.model.records = list(self.data.get(kind, [])) if self.ready else []
        self.model.endResetModel()
        self.status.setText(f"{len(self.model.records)} mục · {self.kind.currentText()}")
        self.selection_changed()

    def add(self):
        self.form(None)

    def edit(self):
        record = self.selected(self.table)
        if record:
            self.form(record)

    def form(self, record):
        if not self.ready or self.current_profile["role"] != "admin":
            return
        kind = self.kind.currentData()
        original = record or {}
        if kind == "staff" and original.get("role") == "admin":
            self.error("Không thay đổi tài khoản chủ chuỗi qua màn hình này.")
            return
        branches = [(b["name"], b["id"]) for b in self.data.get("branches", [])]
        fields = {
            "branches": [
                ("name", "Tên chi nhánh", original.get("name")),
                ("address", "Địa chỉ", original.get("address")),
            ],
            "shifts": [
                ("branch", "Chi nhánh", branches),
                ("name", "Tên ca", original.get("name")),
                ("start", "Bắt đầu HH:MM", str(original.get("start_time", "08:00"))[:5]),
                ("end", "Kết thúc HH:MM", str(original.get("end_time", "16:00"))[:5]),
            ],
            "devices": [
                ("branch", "Chi nhánh", branches),
                ("name", "Tên máy", original.get("device_name")),
                ("uuid", "Mã máy", original.get("device_uuid", self.current_device_uuid)),
                ("active", "Trạng thái", [("Hoạt động", True), ("Tạm khóa", False)]),
            ],
            "staff": [
                ("name", "Họ tên", original.get("full_name")),
                ("branch", "Chi nhánh", branches),
                ("role", "Vai trò", [("Dược sĩ", "staff"), ("Quản lý chi nhánh", "storemanager")]),
                ("phone", "Điện thoại", original.get("phone")),
                ("active", "Trạng thái", [("Hoạt động", True), ("Tạm khóa", False)]),
            ],
        }[kind]
        if record is None and kind in ("staff", "devices"):
            fields = [field for field in fields if field[0] != "active"]
        if kind == "staff" and record is None:
            fields = [("email", "Email", ""), ("password", "Mật khẩu (ít nhất 12 ký tự)", "")] + fields
        dialog = FormDialog(
            self, ("Chỉnh sửa " if record else "Thêm ") + self.kind.currentText().lower(), fields
        )
        for key, value in [
            ("branch", original.get("branch_id")),
            ("role", original.get("role")),
            ("active", original.get("is_active", True)),
        ]:
            if key in dialog.fields:
                index = dialog.fields[key].findData(value)
                if index >= 0:
                    dialog.fields[key].setCurrentIndex(index)
        if record and kind == "devices":
            dialog.fields["uuid"].setEnabled(False)

        def save():
            values = dialog.values()
            if not values.get("name") or (kind != "branches" and not values.get("branch")):
                dialog.message.setText("Nhập tên và chọn chi nhánh hợp lệ.")
                return
            if kind == "shifts":
                try:
                    start, end = time.fromisoformat(values["start"]), time.fromisoformat(values["end"])
                    if start == end:
                        raise ValueError()
                except ValueError:
                    dialog.message.setText("Nhập giờ HH:MM hợp lệ. Giờ bắt đầu và kết thúc phải khác nhau.")
                    return
            if kind == "devices" and not values.get("uuid"):
                dialog.message.setText("Nhập mã nhận diện máy.")
                return
            if (
                kind == "staff"
                and record is None
                and (
                    "@" not in values["email"]
                    or len(values["password"]) < 12
                    or len(values["password"].encode("utf-8")) > 72
                )
            ):
                dialog.message.setText("Nhập email hợp lệ và mật khẩu từ 12 ký tự, tối đa 72 byte.")
                return
            record_id = original.get("id")

            def work():
                if kind == "branches":
                    return (
                        self.supabase.update_branch(record_id, values["name"], values["address"])
                        if record
                        else self.supabase.create_branch(values["name"], values["address"])
                    )
                if kind == "shifts":
                    args = (values["branch"], values["name"], values["start"], values["end"])
                    return (
                        self.supabase.update_shift(record_id, *args)
                        if record
                        else self.supabase.create_shift(*args)
                    )
                if kind == "devices":
                    return (
                        self.supabase.update_device(
                            record_id, values["branch"], values["name"], values["active"]
                        )
                        if record
                        else self.supabase.register_device(values["branch"], values["uuid"], values["name"])
                    )
                if record:
                    return self.supabase.update_user_full(
                        record_id,
                        values["name"],
                        values["role"],
                        values["branch"],
                        values["phone"],
                        values["active"],
                    )
                return self.supabase.create_user(
                    values["email"],
                    values["password"],
                    values["name"],
                    values["role"],
                    values["branch"],
                    values["phone"],
                )

            dialog.save(work, self.refresh)

        dialog.buttons.accepted.connect(save)
        dialog.exec()
        dialog.deleteLater()

    def delete(self):
        record = self.selected(self.table)
        if not record or self.current_profile["role"] != "admin":
            return
        kind = self.kind.currentData()
        if kind == "staff" and record.get("role") == "admin":
            return
        if (
            QMessageBox.question(
                self,
                "Xác nhận xóa",
                "Xóa mục đã chọn? Thao tác có thể ảnh hưởng dữ liệu liên quan.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        methods = {
            "branches": self.supabase.delete_branch,
            "shifts": self.supabase.delete_shift,
            "devices": self.supabase.delete_device,
            "staff": self.supabase.delete_user_full,
        }
        method, record_id = methods[kind], record["id"]
        self.mutate(
            lambda: method(record_id), self.refresh, [self.add_btn, self.edit_btn, self.delete_btn, self.kind]
        )
