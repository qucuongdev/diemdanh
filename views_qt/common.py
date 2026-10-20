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
        value = self.columns[index.column()][1](self.records[index.row()])
        return str(value if value is not None else "—")

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columns[section][0]
        return None

    def replace(self, records):
        self.beginResetModel()
        self.records = list(records)
        self.endResetModel()


def table_for(model):
    table = QTableView()
    table.setModel(model)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setWordWrap(False)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(42)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setDefaultSectionSize(150)
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
        self.status = label()

    def heading(self, title, subtitle):
        self.root.addWidget(label(title, True))
        self.root.addWidget(label(subtitle))

    def error(self, message):
        self.status.setText(message)
        self.status.setProperty("error", True)

    def selected(self, table):
        rows = table.selectionModel().selectedRows()
        return table.model().records[rows[0].row()] if rows else None

    def mutate(self, work, on_done, controls=(), owner=None):
        runner = self.tasks if owner is None else owner.tasks
        for control in controls:
            control.setEnabled(False)

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
        if not accepted:
            restore()
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
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def values(self):
        return {
            key: w.currentData() if isinstance(w, QComboBox) else w.text().strip()
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
