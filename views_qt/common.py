"""Shared native Qt tables, forms and task-aware page behavior."""

from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QComboBox,
    QLineEdit,
)
from core.qt_worker import TaskRunner


class TableModel(QAbstractTableModel):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.records = []

    def rowCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.records)

    def columnCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        column = self.columns[index.column()]
        renderer = column[2] if role == Qt.ItemDataRole.ToolTipRole and len(column) > 2 else column[1]
        value = renderer(self.records[index.row()])
        return str(value if value is not None else "—")

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columns[section][0]
        return None

    def replace(self, records):
        self.beginResetModel()
        self.records = list(records)
        self.endResetModel()


class DataTableView(QTableView):
    """Fit a small set of columns without scanning records or adding row widgets."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_columns()

    def fit_columns(self):
        model = self.model()
        if model is None or not model.columnCount():
            return
        widths = {
            "Nhân viên": (280, 160), "Họ tên": (280, 160), "Chi nhánh": (320, 180),
            "Địa chỉ": (360, 180), "Nội dung": (360, 180), "Trạng thái": (240, 150),
            "Mã máy": (300, 180), "Tên máy": (220, 160), "Ca": (180, 120),
            "Ca làm": (180, 120), "Tên ca": (180, 120), "Điện thoại": (160, 130),
            "Ngày": (130, 110), "Ngày ca": (130, 110), "Muộn (giờ:phút)": (190, 150),
            "Trạng thái (giờ:phút)": (280, 210),
        }
        sizes = [widths.get(column[0], (110, 80)) for column in model.columns]
        minimum = [max(size[1], self.fontMetrics().horizontalAdvance(column[0]) + 28)
                   for size, column in zip(sizes, model.columns, strict=True)]
        available = max(self.viewport().width(), sum(minimum))
        remaining = available
        extra = available - sum(minimum)
        total = sum(size[0] for size in sizes)
        for index, (preferred, smallest) in enumerate(zip(sizes, minimum, strict=True)):
            size = remaining if index == len(sizes) - 1 else smallest + int(extra * preferred[0] / total)
            self.setColumnWidth(index, size)
            remaining -= size


def table_for(model):
    table = DataTableView()
    table.setModel(model)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setWordWrap(False)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(42)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.horizontalHeader().setStretchLastSection(False)
    table.horizontalHeader().setMinimumSectionSize(80)
    model.modelReset.connect(table.fit_columns)
    table.fit_columns()
    return table


def label(text="", title=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if title:
        widget.setObjectName("PageTitle")
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.setMinimumHeight(36)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        widget.setProperty("primary", True)
    widget.clicked.connect(callback)
    return widget


class StatusLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)

    def setText(self, text):
        self.setProperty("error", False)
        super().setText(text)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_error(self, text):
        self.setText(text)
        self.setProperty("error", True)
        self.style().unpolish(self)
        self.style().polish(self)


class Page(QWidget):
    def __init__(self, parent=None, current_profile=None):
        super().__init__(parent)
        from core.supabase_service import SupabaseService

        self.current_profile = current_profile or {}
        self.supabase = SupabaseService()
        self.tasks = TaskRunner(self)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 24, 24, 24)
        self.root.setSpacing(16)
        self.status = StatusLabel()

    def heading(self, title, subtitle):
        self.root.addWidget(label(title, True))
        self.root.addWidget(label(subtitle))

    def error(self, message):
        self.status.set_error(message)

    def selected(self, table):
        rows = table.selectionModel().selectedRows()
        return table.model().records[rows[0].row()] if rows else None

    def mutate(self, work, on_done, controls=(), owner=None):
        runner = self.tasks if owner is None else owner.tasks

        def restore():
            for control in controls:
                control.setEnabled(True)

        def failed(message):
            restore()
            self.error(message)

        def done(result):
            restore()
            if not isinstance(result, dict) or not result.get("success"):
                failed((result or {}).get("message", "Thao tác không thành công."))
                return
            self.status.setText("Đã lưu thay đổi.")
            on_done()

        accepted = runner.submit("mutation", work, done, failed, replace=False)
        if accepted:
            for control in controls:
                control.setEnabled(False)
        return accepted


class FormDialog(QDialog):
    """Small form; read widget values before submitting background work."""

    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.tasks = TaskRunner(self)
        self.fields = {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)
        for key, caption, value in fields:
            if isinstance(value, list):
                widget = QComboBox()
                for text, data in value:
                    widget.addItem(text, data)
            else:
                widget = QLineEdit(str(value or ""))
                if key == "password":
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
            self.fields[key] = widget
            form.addRow(caption, widget)
        layout.addLayout(form)
        self.message = label()
        layout.addWidget(self.message)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Lưu")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def values(self):
        return {
            key: (w.currentData() if isinstance(w, QComboBox)
                  else w.text() if key == "password" else w.text().strip())
            for key, w in self.fields.items()
        }

    def save(self, work, on_success):
        self.buttons.setEnabled(False)

        def error(message):
            self.buttons.setEnabled(True)
            self.message.setText(message)

        def done(result):
            if not result.get("success"):
                error(result.get("message", "Không thể lưu thay đổi."))
                return
            self.accept()
            on_success()

        self.tasks.submit("save", work, done, error, replace=False)

    def done(self, result):
        if self.tasks._active:
            self.message.setText("Đang lưu, vui lòng chờ hoàn tất.")
            return
        self.tasks.invalidate()
        super().done(result)
