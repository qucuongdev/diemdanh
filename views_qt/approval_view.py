import webbrowser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTabWidget, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt
from core.supabase_service import SupabaseService
from core.qt_worker import QtWorker

class ApprovalView(QWidget):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent)
        self.current_profile = current_profile or {}
        self.supabase = SupabaseService()
        self.branch_id = self.current_profile.get("branch_id")
        self.user_role = self.current_profile.get("role", "storemanager")
        self.worker_leave = None
        self.worker_proof = None

        self.setup_ui()
        self.refresh_all()

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

        lbl_title = QLabel("📋 TRUNG TÂM PHÊ DUYỆT YÊU CẦU")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; border: none;")
        h_layout.addWidget(lbl_title)

        h_layout.addStretch()

        btn_refresh = QPushButton("🔄 Làm mới")
        btn_refresh.setFixedSize(100, 34)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #333333; color: white; font-weight: bold;
                border-radius: 6px; border: none; font-size: 13px;
            }
            QPushButton:hover { background-color: #444444; }
        """)
        btn_refresh.clicked.connect(self.refresh_all)
        h_layout.addWidget(btn_refresh)

        root_layout.addWidget(header)

        # 2. Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #242424;
                border-radius: 12px;
            }
        """)

        # Tab 1: Đơn xin nghỉ phép
        self.tab_leave = QWidget()
        tl_layout = QVBoxLayout(self.tab_leave)
        tl_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_leave = QScrollArea()
        self.scroll_leave.setWidgetResizable(True)
        self.content_leave = QWidget()
        self.layout_leave = QVBoxLayout(self.content_leave)
        self.layout_leave.setSpacing(8)
        self.scroll_leave.setWidget(self.content_leave)
        tl_layout.addWidget(self.scroll_leave)

        self.tab_widget.addTab(self.tab_leave, "Đơn xin nghỉ phép")

        # Tab 2: Giải trình quên chấm công
        self.tab_proof = QWidget()
        tp_layout = QVBoxLayout(self.tab_proof)
        tp_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_proof = QScrollArea()
        self.scroll_proof.setWidgetResizable(True)
        self.content_proof = QWidget()
        self.layout_proof = QVBoxLayout(self.content_proof)
        self.layout_proof.setSpacing(8)
        self.scroll_proof.setWidget(self.content_proof)
        tp_layout.addWidget(self.scroll_proof)

        self.tab_widget.addTab(self.tab_proof, "Giải trình quên chấm công (Kèm ảnh)")

        root_layout.addWidget(self.tab_widget)

    def refresh_all(self):
        self.load_leave_requests()
        self.load_attendance_proofs()

    # ================= TAB 1: DUYỆT ĐƠN NGHỈ =================
    def load_leave_requests(self):
        while self.layout_leave.count():
            item = self.layout_leave.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl_loading = QLabel("⏳ Đang tải danh sách đơn xin nghỉ...")
        lbl_loading.setStyleSheet("font-size: 13px; color: gray; padding: 40px;")
        lbl_loading.setAlignment(Qt.AlignCenter)
        self.layout_leave.addWidget(lbl_loading)

        b_id = self.branch_id if self.user_role != "admin" else None

        def fetch():
            return self.supabase.get_leave_requests(branch_id=b_id)

        def on_done(requests):
            while self.layout_leave.count():
                item = self.layout_leave.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not requests:
                lbl = QLabel("Không có đơn xin nghỉ nào cần duyệt.")
                lbl.setStyleSheet("font-size: 13px; color: gray; padding: 40px;")
                lbl.setAlignment(Qt.AlignCenter)
                self.layout_leave.addWidget(lbl)
                return

            for req in requests:
                card = self._create_leave_card(req)
                self.layout_leave.addWidget(card)

            self.layout_leave.addStretch()

        self.worker_leave = QtWorker(fetch)
        self.worker_leave.result_ready.connect(on_done)
        self.worker_leave.start()

    def _create_leave_card(self, req):
        card = QFrame()
        card.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px; padding: 12px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(8)

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

        lbl_t = QLabel(f"👤 {staff_name}  •  🏥 {branch_name}  •  Loại: {type_str}")
        lbl_t.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; border: none;")
        c_layout.addWidget(lbl_t)

        lbl_info = QLabel(f"📅 Ngày nghỉ: {work_date} ({shift_name})\n💬 Lý do: {reason}")
        lbl_info.setStyleSheet("font-size: 12px; color: #CCCCCC; border: none;")
        c_layout.addWidget(lbl_info)

        act_box = QWidget()
        act_box.setStyleSheet("border: none;")
        a_layout = QHBoxLayout(act_box)
        a_layout.setContentsMargins(0, 4, 0, 0)
        a_layout.addStretch()

        if status == "pending":
            btn_app = QPushButton("✅ Phê duyệt")
            btn_app.setFixedSize(110, 32)
            btn_app.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px;")
            btn_app.clicked.connect(lambda: self.handle_review_leave(req, "approved"))
            a_layout.addWidget(btn_app)

            btn_rej = QPushButton("❌ Từ chối")
            btn_rej.setFixedSize(100, 32)
            btn_rej.setStyleSheet("background-color: #DC3545; color: white; font-weight: bold; border-radius: 6px;")
            btn_rej.clicked.connect(lambda: self.handle_review_leave(req, "rejected"))
            a_layout.addWidget(btn_rej)
        else:
            st_col = "#28A745" if status == "approved" else "#DC3545"
            st_txt = "ĐÃ DUYỆT" if status == "approved" else "ĐÃ TỪ CHỐI"
            badge = QLabel(st_txt)
            badge.setStyleSheet(f"color: {st_col}; font-weight: bold; font-size: 13px;")
            a_layout.addWidget(badge)

        c_layout.addWidget(act_box)
        return card

    def handle_review_leave(self, req, status):
        reviewer_id = self.current_profile.get("id")
        req_id = req.get("id")

        def worker():
            return self.supabase.review_leave_request(req_id, status, reviewer_id)

        def on_done(res):
            if res.get("success"):
                action_name = "phê duyệt" if status == "approved" else "từ chối"
                QMessageBox.information(self, "Thành công", f"Đã {action_name} đơn xin nghỉ!")
                self.load_leave_requests()
            else:
                QMessageBox.critical(self, "Thông báo", res.get("message", "Không thể cập nhật trạng thái đơn."))

        w = QtWorker(worker)
        w.result_ready.connect(on_done)
        w.start()
        # Lưu reference để không bị GC thu hồi
        self._temp_worker = w

    # ================= TAB 2: DUYỆT MINH CHỨNG & ẢNH =================
    def load_attendance_proofs(self):
        while self.layout_proof.count():
            item = self.layout_proof.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl_loading = QLabel("⏳ Đang tải danh sách minh chứng quên chấm công...")
        lbl_loading.setStyleSheet("font-size: 13px; color: gray; padding: 40px;")
        lbl_loading.setAlignment(Qt.AlignCenter)
        self.layout_proof.addWidget(lbl_loading)

        b_id = self.branch_id if self.user_role != "admin" else None

        def fetch():
            return self.supabase.get_attendance_proofs(branch_id=b_id)

        def on_done(proofs):
            while self.layout_proof.count():
                item = self.layout_proof.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not proofs:
                lbl = QLabel("Không có giải trình quên chấm công nào cần duyệt.")
                lbl.setStyleSheet("font-size: 13px; color: gray; padding: 40px;")
                lbl.setAlignment(Qt.AlignCenter)
                self.layout_proof.addWidget(lbl)
                return

            for p in proofs:
                card = self._create_proof_card(p)
                self.layout_proof.addWidget(card)

            self.layout_proof.addStretch()

        self.worker_proof = QtWorker(fetch)
        self.worker_proof.result_ready.connect(on_done)
        self.worker_proof.start()

    def _create_proof_card(self, p):
        card = QFrame()
        card.setStyleSheet("background-color: #242424; border: 1px solid #333333; border-radius: 10px; padding: 12px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(8)

        staff_name = p.get("profiles", {}).get("full_name", "Nhân viên")
        branch_name = p.get("branches", {}).get("name", "")
        image_url = p.get("image_url", "")
        note = p.get("note", "Không có ghi chú")
        created_at = p.get("created_at", "")[:19].replace("T", " ")
        status = p.get("status", "pending")

        lbl_t = QLabel(f"👤 {staff_name}  •  🏥 {branch_name}  •  Thời gian gửi: {created_at}")
        lbl_t.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; border: none;")
        c_layout.addWidget(lbl_t)

        lbl_note = QLabel(f"💬 Giải trình: {note}")
        lbl_note.setStyleSheet("font-size: 12px; color: #CCCCCC; border: none;")
        c_layout.addWidget(lbl_note)

        act_box = QWidget()
        act_box.setStyleSheet("border: none;")
        a_layout = QHBoxLayout(act_box)
        a_layout.setContentsMargins(0, 4, 0, 0)

        btn_view_img = QPushButton("🖼️ Xem ảnh bằng chứng")
        btn_view_img.setFixedSize(160, 32)
        btn_view_img.setStyleSheet("background-color: #1F6AA5; color: white; font-weight: bold; border-radius: 6px;")
        btn_view_img.clicked.connect(lambda: webbrowser.open(image_url))
        a_layout.addWidget(btn_view_img)

        a_layout.addStretch()

        if status == "pending":
            btn_app = QPushButton("✅ Duyệt công")
            btn_app.setFixedSize(110, 32)
            btn_app.setStyleSheet("background-color: #28A745; color: white; font-weight: bold; border-radius: 6px;")
            btn_app.clicked.connect(lambda: self.handle_review_proof(p, "approved"))
            a_layout.addWidget(btn_app)

            btn_rej = QPushButton("❌ Từ chối")
            btn_rej.setFixedSize(100, 32)
            btn_rej.setStyleSheet("background-color: #DC3545; color: white; font-weight: bold; border-radius: 6px;")
            btn_rej.clicked.connect(lambda: self.handle_review_proof(p, "rejected"))
            a_layout.addWidget(btn_rej)
        else:
            st_col = "#28A745" if status == "approved" else "#DC3545"
            st_txt = "ĐÃ DUYỆT" if status == "approved" else "ĐÃ TỪ CHỐI"
            badge = QLabel(st_txt)
            badge.setStyleSheet(f"color: {st_col}; font-weight: bold; font-size: 13px;")
            a_layout.addWidget(badge)

        c_layout.addWidget(act_box)
        return card

    def handle_review_proof(self, p, status):
        reviewer_id = self.current_profile.get("id")
        proof_id = p.get("id")

        def worker():
            return self.supabase.review_attendance_proof(proof_id, status, reviewer_id)

        def on_done(res):
            if res.get("success"):
                action_name = "duyệt" if status == "approved" else "từ chối"
                QMessageBox.information(self, "Thành công", f"Đã {action_name} minh chứng!")
                self.load_attendance_proofs()
            else:
                QMessageBox.critical(self, "Thông báo", res.get("message", "Không thể cập nhật trạng thái minh chứng."))

        w = QtWorker(worker)
        w.result_ready.connect(on_done)
        w.start()
        self._temp_worker = w
