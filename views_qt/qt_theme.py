"""Application-wide light/dark themes, shared tokens and persistent preference."""

import os
from pathlib import Path
from string import Template

from PySide6.QtCore import QObject, QLocale, QSettings, Signal, Slot
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QPushButton


THEMES = {
    "dark": {
        "window": "#111827", "surface": "#172033", "alternate": "#1c2840",
        "text": "#e5e7eb", "title": "#f8fafc", "muted": "#a3b1c6",
        "border": "#3b4961", "subtle": "#2b364c", "button": "#253149",
        "hover": "#334361", "disabled": "#1d2738", "disabled_text": "#93a2b8",
        "accent": "#2563eb", "accent_hover": "#1d4ed8", "accent_border": "#3b82f6",
        "focus": "#93c5fd", "selection": "#244786", "selection_text": "#ffffff",
        "header": "#202d44", "header_text": "#cbd5e1", "clock": "#93c5fd",
        "error": "#fca5a5", "weekend": "#fda4af", "success": "#86efac",
    },
    "light": {
        "window": "#f3f6fa", "surface": "#ffffff", "alternate": "#f1f5f9",
        "text": "#1e293b", "title": "#0f172a", "muted": "#475569",
        "border": "#b6c4d6", "subtle": "#d7e0eb", "button": "#e2e8f0",
        "hover": "#cbd5e1", "disabled": "#edf2f7", "disabled_text": "#64748b",
        "accent": "#1d4ed8", "accent_hover": "#1e40af", "accent_border": "#1d4ed8",
        "focus": "#2563eb", "selection": "#dbeafe", "selection_text": "#172554",
        "header": "#e8eef6", "header_text": "#334155", "clock": "#1d4ed8",
        "error": "#b91c1c", "weekend": "#b91c1c", "success": "#166534",
    },
}

STYLESHEET = Template("""
QWidget { background: $window; color: $text; font-family: 'Segoe UI'; font-size: 14px; }
QMainWindow, QDialog { background: $window; }
QWidget#Sidebar { background: $surface; border-right: 1px solid $subtle; }
QLabel { background: transparent; border: none; }
QLabel[error="true"] { color: $error; }
QLabel#PageTitle { color: $title; font-size: 26px; font-weight: 600; }
QLabel#Clock { font-size: 48px; font-weight: 600; color: $clock; }
QLabel#SidebarLogo { font-size: 20px; font-weight: 600; }
QFrame#Card, QFrame#LoginCard { background: $surface; border: 1px solid $subtle; border-radius: 12px; }
QPushButton { background: $button; border: 1px solid $border; border-radius: 7px; padding: 8px 14px; }
QPushButton:hover { background: $hover; }
QPushButton:focus { border-color: $focus; }
QPushButton:disabled { background: $disabled; color: $disabled_text; border-color: $subtle; }
QPushButton[primary="true"], QPushButton[active="true"] { background: $accent; color: #ffffff; border-color: $accent_border; }
QPushButton[primary="true"]:hover, QPushButton[active="true"]:hover { background: $accent_hover; }
QPushButton[primary="true"]:disabled { background: $disabled; color: $disabled_text; border-color: $border; }
QLineEdit, QComboBox, QDateEdit, QTimeEdit { background: $surface; border: 1px solid $border; border-radius: 6px; padding: 7px; min-height: 20px; selection-background-color: $accent; selection-color: #ffffff; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus { border-color: $focus; }
QLineEdit:disabled, QComboBox:disabled { background: $disabled; color: $disabled_text; }
QComboBox QAbstractItemView { background: $surface; color: $text; selection-background-color: $selection; selection-color: $selection_text; }
QTableView { background: $surface; alternate-background-color: $alternate; border: 1px solid $subtle; border-radius: 8px; gridline-color: $subtle; selection-background-color: $selection; selection-color: $selection_text; }
QTableView::item { padding: 6px; }
QTableView::item:selected { background: $selection; color: $selection_text; }
QHeaderView::section { background: $header; color: $header_text; border: none; border-bottom: 1px solid $border; padding: 10px; font-weight: 600; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: $surface; color: $muted; padding: 10px 20px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: $clock; border-bottom-color: $focus; }
QCalendarWidget QWidget { background: $surface; }
QCalendarWidget QToolButton { color: $text; background: $surface; padding: 5px; border-radius: 4px; }
QCalendarWidget QToolButton:hover { background: $hover; }
QCalendarWidget QAbstractItemView { background: $surface; color: $text; selection-background-color: $selection; selection-color: $selection_text; }
QCalendarWidget QAbstractItemView::item { padding: 0px; }
QMenu { background: $surface; color: $text; border: 1px solid $border; }
QMenu::item:selected { background: $selection; color: $selection_text; }
QScrollArea { border: none; }
QScrollBar:vertical { background: $surface; width: 10px; }
QScrollBar:horizontal { background: $surface; height: 10px; }
QScrollBar::handle { background: $border; border-radius: 4px; }
QScrollBar::handle:vertical { min-height: 28px; }
QScrollBar::handle:horizontal { min-width: 28px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
QToolTip { background: $button; color: $text; border: 1px solid $border; }
""")


class ThemeManager(QObject):
    changed = Signal(str)

    def __init__(self, app, settings=None):
        super().__init__(app)
        self.app = app
        # Tests and benchmarks never read or change the user's saved preference.
        self.settings = settings
        if self.settings is None and os.getenv("ATTENDANCE_TESTING") != "1":
            self.settings = QSettings("NhaThuoc", "AttendanceDesktop")
        saved = self.settings.value("appearance/theme", "dark") if self.settings is not None else "dark"
        self.mode = saved if isinstance(saved, str) and saved in THEMES else "dark"
        self.apply()

    @property
    def colors(self):
        return THEMES[self.mode]

    def apply(self):
        colors = self.colors
        palette = QPalette()
        roles = {
            "Window": "window", "WindowText": "text", "Base": "surface",
            "AlternateBase": "alternate", "Text": "text", "Button": "button",
            "ButtonText": "text", "ToolTipBase": "button", "ToolTipText": "text",
            "Highlight": "selection", "HighlightedText": "selection_text",
            "Link": "clock", "PlaceholderText": "muted", "BrightText": "error",
        }
        for role, token in roles.items():
            palette.setColor(getattr(QPalette.ColorRole, role), QColor(colors[token]))
        for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled_text"]))
        self.app.setPalette(palette)
        self.app.setStyleSheet(STYLESHEET.substitute(colors))
        self.app.setProperty("appearanceTheme", self.mode)
        self.changed.emit(self.mode)

    @Slot(str)
    def set_mode(self, mode):
        if mode not in THEMES:
            raise ValueError("Unknown theme")
        if mode == self.mode:
            return
        self.mode = mode
        if self.settings is not None:
            self.settings.setValue("appearance/theme", mode)
        self.apply()

    @Slot()
    def toggle(self):
        self.set_mode("light" if self.mode == "dark" else "dark")


def configure_application(app):
    if hasattr(app, "theme_manager"):
        return app.theme_manager
    QLocale.setDefault(QLocale(QLocale.Language.Vietnamese, QLocale.Country.Vietnam))
    if not QFontDatabase.families():
        font = Path("C:/Windows/Fonts/segoeui.ttf")
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.theme_manager = ThemeManager(app)
    return app.theme_manager


class ThemeToggleButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)
        self.setCheckable(True)
        self.manager = configure_application(QApplication.instance())
        self.clicked.connect(self.manager.toggle)
        self.manager.changed.connect(self.update_mode)
        self.update_mode(self.manager.mode)

    @Slot(str)
    def update_mode(self, mode):
        target = "sáng" if mode == "dark" else "tối"
        self.setText(f"Giao diện {target}")
        self.setChecked(mode == "light")
        self.setToolTip(f"Chuyển sang giao diện {target}")
        self.setAccessibleName(f"Chuyển sang giao diện {target}")
        self.setAccessibleDescription(f"Giao diện hiện tại: {'tối' if mode == 'dark' else 'sáng'}")
