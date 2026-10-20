from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QComboBox, QMessageBox
from views_qt.common import Page, TableModel, table_for, button

STATUS = {"pending": "Chờ duyệt", "approved": "Đã duyệt", "rejected": "Đã từ chối"}


class ApprovalView(Page):
    PAGE_SIZE = 50

    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent, current_profile)
        self.offset = 0
        self.busy = False
        self.has_more = False
        self.heading("Duyệt yêu cầu", "Chọn một yêu cầu để xem lý do, ảnh minh chứng và xử lý.")
        controls = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItem("Đơn xin nghỉ", "leave")
        self.kind.addItem("Giải trình chấm công", "proof")
        self.state = QComboBox()
        for value, caption in STATUS.items():
            self.state.addItem(caption, value)
        controls.addWidget(self.kind)
        controls.addWidget(self.state)
        self.refresh_btn = button("Làm mới", self.reset)
        controls.addWidget(self.refresh_btn)
        controls.addStretch()
        self.root.addLayout(controls)
        self.model = TableModel(
            [
                ("Nhân viên", lambda r: (r.get("profiles") or {}).get("full_name")),
                ("Chi nhánh", lambda r: (r.get("branches") or {}).get("name")),
                (
                    "Ngày ca",
                    lambda r: (
                        (r.get("schedules") or {}).get("work_date") or str(r.get("created_at", ""))[:10]
                    ),
                ),
                ("Nội dung", lambda r: r.get("reason") or r.get("note")),
                ("Trạng thái", lambda r: STATUS.get(r.get("status"), "Không rõ")),
            ],
            self,
        )
        self.table = table_for(self.model)
        self.root.addWidget(self.table, 1)
        self.root.addWidget(self.status)
        footer = QHBoxLayout()
        self.prev_btn = button("Trang trước", lambda: self.move(-1))
        self.next_btn = button("Trang sau", lambda: self.move(1))
        self.details_btn = button("Xem chi tiết", self.details)
        self.image_btn = button("Xem ảnh", self.open_image)
        self.reject_btn = button("Từ chối", lambda: self.review("rejected"))
        self.approve_btn = button("Phê duyệt", lambda: self.review("approved"), True)
        for widget in [
            self.prev_btn,
            self.next_btn,
            self.details_btn,
            self.image_btn,
            self.reject_btn,
            self.approve_btn,
        ]:
            footer.addWidget(widget)
        self.root.addLayout(footer)
        self.kind.currentIndexChanged.connect(self.reset)
        self.state.currentIndexChanged.connect(self.reset)
        self.table.selectionModel().selectionChanged.connect(self.selection_changed)
        self.selection_changed()
        self.reset()

    def on_show(self):
        if not self.busy:
            self.reset()

    def on_hide(self):
        self.tasks.cancel("image")

    def reset(self, *_):
        self.tasks.cancel("image")
        self.offset = 0
        self.load_data()

    def move(self, direction):
        self.offset = max(0, self.offset + direction * self.PAGE_SIZE)
        self.load_data()

    def load_data(self):
        if self.current_profile.get("role") not in ("admin", "storemanager"):
            self.error("Bạn không có quyền duyệt yêu cầu.")
            return
        branch = None if self.current_profile["role"] == "admin" else self.current_profile["branch_id"]
        kind, status, offset = self.kind.currentData(), self.state.currentData(), self.offset
        self.tasks.cancel("image")
        method = self.supabase.get_leave_requests if kind == "leave" else self.supabase.get_attendance_proofs
        self.status.setText("Đang tải yêu cầu…")
        self.busy = True
        self.selection_changed()
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)

        def done(records):
            self.busy = False
            self.has_more = len(records) > self.PAGE_SIZE
            self.model.replace(records[: self.PAGE_SIZE])
            self.prev_btn.setEnabled(offset > 0)
            self.next_btn.setEnabled(self.has_more)
            self.status.setText(
                f"Trang {offset // self.PAGE_SIZE + 1} · {min(len(records), self.PAGE_SIZE)} yêu cầu"
                if records
                else "Không có yêu cầu phù hợp."
            )
            self.selection_changed()

        def failed(message):
            self.busy = False
            self.has_more = False
            self.model.replace([])
            self.prev_btn.setEnabled(offset > 0)
            self.error(message)
            self.selection_changed()

        self.tasks.submit(
            "list",
            lambda: method(branch_id=branch, status=status, limit=self.PAGE_SIZE + 1, offset=offset),
            done,
            failed,
        )

    def selection_changed(self, *_):
        self.tasks.cancel("image")
        record = self.selected(self.table)
        actionable = (bool(record) and record.get("status") == "pending" and not self.busy
                      and record.get("user_id") != self.current_profile["id"])
        self.approve_btn.setEnabled(actionable)
        self.reject_btn.setEnabled(actionable)
        self.details_btn.setEnabled(bool(record) and not self.busy)
        self.image_btn.setEnabled(bool(record) and self.kind.currentData() == "proof" and not self.busy)

    def details(self):
        record = self.selected(self.table)
        if record:
            box = QMessageBox(self)
            box.setWindowTitle("Chi tiết yêu cầu")
            from PySide6.QtCore import Qt

            box.setTextFormat(Qt.TextFormat.PlainText)
            box.setText(record.get("reason") or record.get("note") or "Không có nội dung.")
            box.exec()

    def review(self, status):
        record = self.selected(self.table)
        if (self.busy or not record or record.get("status") != "pending"
                or record.get("user_id") == self.current_profile["id"]):
            return
        kind = self.kind.currentData()
        method = (
            self.supabase.review_leave_request if kind == "leave" else self.supabase.review_attendance_proof
        )
        record_id, reviewer = record["id"], self.current_profile["id"]
        self.busy = True
        self.selection_changed()
        for control in [self.kind, self.state, self.refresh_btn, self.prev_btn, self.next_btn]:
            control.setEnabled(False)

        def done(result):
            self.busy = False
            for control in [self.kind, self.state, self.refresh_btn]:
                control.setEnabled(True)
            if not result.get("success"):
                self.error(result.get("message", "Không thể duyệt yêu cầu."))
                self.selection_changed()
                self.prev_btn.setEnabled(self.offset > 0)
                self.next_btn.setEnabled(self.has_more)
                return
            self.load_data()

        def failed(message):
            done({"success": False, "message": message})

        self.tasks.submit("review", lambda: method(record_id, status, reviewer), done, failed, replace=False)

    def open_image(self):
        record = self.selected(self.table)
        if not record:
            return
        path = record.get("image_url")
        self.image_btn.setEnabled(False)

        def done(url):
            self.selection_changed()
            if not url or not QDesktopServices.openUrl(QUrl(url)):
                self.error("Không thể mở ảnh minh chứng.")

        def failed(message):
            self.selection_changed()
            self.error(message)

        self.tasks.submit("image", lambda: self.supabase.get_proof_url(path), done, failed)
