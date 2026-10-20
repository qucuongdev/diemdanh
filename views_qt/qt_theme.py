"""One shared palette and application locale for all screens."""


def configure_application(app):
    from pathlib import Path
    from PySide6.QtCore import QLocale
    from PySide6.QtGui import QFont, QFontDatabase

    QLocale.setDefault(QLocale(QLocale.Language.Vietnamese, QLocale.Country.Vietnam))
    # Offscreen Windows tests do not enumerate native fonts automatically.
    if not QFontDatabase.families():
        font = Path("C:/Windows/Fonts/segoeui.ttf")
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(DARK_STYLESHEET)

DARK_STYLESHEET = """
QWidget { background: #111827; color: #e5e7eb; font-family: 'Segoe UI'; font-size: 14px; }
QMainWindow, QDialog { background: #111827; }
QWidget#Sidebar { background: #172033; border-right: 1px solid #2b364c; }
QLabel { background: transparent; border: none; }
QLabel#PageTitle { color: #f8fafc; font-size: 26px; font-weight: 600; }
QLabel#Clock { font-size: 48px; font-weight: 600; color: #93c5fd; }
QLabel#SidebarLogo { font-size: 20px; font-weight: 600; }
QFrame#Card, QFrame#LoginCard { background: #172033; border: 1px solid #2b364c; border-radius: 12px; }
QPushButton { background: #253149; border: 1px solid #36445d; border-radius: 7px; padding: 8px 14px; }
QPushButton:hover { background: #334361; }
QPushButton:focus { border: 1px solid #93c5fd; }
QPushButton:disabled { background: #1d2738; color: #718096; border-color: #2b364c; }
QPushButton[primary="true"], QPushButton[active="true"] { background: #2563eb; color: #ffffff; border-color: #3b82f6; }
QPushButton[primary="true"]:hover { background: #1d4ed8; }
QPushButton[primary="true"]:disabled { background: #273953; color: #94a3b8; border-color: #36445d; }
QLineEdit, QComboBox, QDateEdit, QTimeEdit { background: #172033; border: 1px solid #3b4961; border-radius: 6px; padding: 7px; min-height: 20px; selection-background-color: #2563eb; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border-color: #60a5fa; }
QComboBox QAbstractItemView { background: #172033; selection-background-color: #2563eb; }
QTableView { background: #172033; alternate-background-color: #1c2840; border: 1px solid #2b364c; border-radius: 8px; gridline-color: #2b364c; selection-background-color: #244786; selection-color: #ffffff; }
QTableView::item { padding: 6px; }
QHeaderView::section { background: #202d44; color: #cbd5e1; border: none; border-bottom: 1px solid #36445d; padding: 10px; font-weight: 600; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #172033; color: #94a3b8; padding: 10px 20px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #bfdbfe; border-bottom-color: #60a5fa; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #172033; width: 10px; }
QScrollBar::handle:vertical { background: #475569; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QToolTip { background: #253149; color: #ffffff; border: 1px solid #475569; }
"""
