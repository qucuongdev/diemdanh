# File giao diện QSS Dark Theme chuẩn mực cho ứng dụng Nhà Thuốc Điểm Danh
# Giữ nguyên toàn bộ bảng màu sắc (Color Palette) và kích thước như bản CustomTkinter

DARK_STYLESHEET = """
QMainWindow, QWidget#CentralWidget {
    background-color: #1A1A1A;
    color: #F0F0F0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* Sidebar bên trái */
QWidget#Sidebar {
    background-color: #242424;
    border-right: 1px solid #333333;
}

QLabel#SidebarLogo {
    color: #FFFFFF;
    font-size: 18px;
    font-weight: bold;
    padding: 10px 0px;
}

QLabel#RoleBadge {
    background-color: #18324F;
    color: #64B5F6;
    border-radius: 6px;
    padding: 5px 10px;
    font-weight: bold;
    font-size: 11px;
}

QPushButton.NavButton {
    background-color: transparent;
    color: #CCCCCC;
    text-align: left;
    padding: 10px 15px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton.NavButton:hover {
    background-color: #333333;
    color: #FFFFFF;
}

QPushButton.NavButton[active="true"] {
    background-color: #1F6AA5;
    color: #FFFFFF;
    font-weight: bold;
}

QPushButton#LogoutSidebarBtn {
    background-color: transparent;
    color: #FF5252;
    text-align: left;
    padding: 10px 15px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: bold;
}

QPushButton#LogoutSidebarBtn:hover {
    background-color: #3E1E1E;
    color: #FF7B7B;
}

/* Các Card khung hình bo góc */
QFrame.CardFrame {
    background-color: #242424;
    border: 1px solid #333333;
    border-radius: 12px;
}

QFrame.SubCard {
    background-color: #1E1E1E;
    border: 1px solid #2E2E2E;
    border-radius: 8px;
}

/* Tiêu đề & Nhãn */
QLabel {
    color: #E0E0E0;
}

QLabel.TitleLabel {
    font-size: 16px;
    font-weight: bold;
    color: #FFFFFF;
}

QLabel.SectionTitle {
    font-size: 14px;
    font-weight: bold;
    color: #FFFFFF;
}

/* Các Nút bấm chung */
QPushButton.PrimaryBtn {
    background-color: #1F6AA5;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton.PrimaryBtn:hover {
    background-color: #257EC4;
}

QPushButton.PrimaryBtn:disabled {
    background-color: #4A4A4A;
    color: #888888;
}

QPushButton.SuccessBtn {
    background-color: #28A745;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton.SuccessBtn:hover {
    background-color: #2EBF4F;
}

QPushButton.SuccessBtn:disabled {
    background-color: #384F3D;
    color: #7A9980;
}

QPushButton.DangerBtn {
    background-color: #DC3545;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton.DangerBtn:hover {
    background-color: #F04153;
}

QPushButton.DangerBtn:disabled {
    background-color: #553337;
    color: #8E6E72;
}

QPushButton.WarningBtn {
    background-color: #FD7E14;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton.WarningBtn:hover {
    background-color: #FF8F33;
}

QPushButton.WarningBtn:disabled {
    background-color: #5A4330;
    color: #8E7A69;
}

QPushButton.InfoBtn {
    background-color: #17A2B8;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton.InfoBtn:hover {
    background-color: #1CB6CF;
}

/* Input Entry & Combobox */
QLineEdit {
    background-color: #2D2D2D;
    border: 1px solid #444444;
    border-radius: 8px;
    padding: 8px 12px;
    color: #FFFFFF;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #1F6AA5;
    background-color: #333333;
}

QComboBox {
    background-color: #2D2D2D;
    border: 1px solid #444444;
    border-radius: 8px;
    padding: 6px 12px;
    color: #FFFFFF;
    font-size: 13px;
    min-height: 24px;
}

QComboBox:hover {
    border: 1px solid #555555;
}

QComboBox QAbstractItemView {
    background-color: #242424;
    color: #FFFFFF;
    selection-background-color: #1F6AA5;
    selection-color: #FFFFFF;
    border: 1px solid #444444;
}

/* QTabWidget */
QTabWidget::pane {
    border: 1px solid #333333;
    background-color: #242424;
    border-radius: 10px;
}

QTabBar::tab {
    background-color: #1E1E1E;
    color: #AAAAAA;
    padding: 9px 20px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: bold;
}

QTabBar::tab:selected {
    background-color: #242424;
    color: #64B5F6;
    border-bottom: 2px solid #64B5F6;
}

QTabBar::tab:hover {
    color: #FFFFFF;
    background-color: #282828;
}

/* Scroll Area & Scrollbar */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical {
    border: none;
    background: #1A1A1A;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #444444;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #666666;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Bảng Table (QTableWidget) */
QTableWidget {
    background-color: #242424;
    border: 1px solid #333333;
    border-radius: 8px;
    gridline-color: #333333;
    color: #E0E0E0;
}

QTableWidget::item {
    padding: 6px;
    border-bottom: 1px solid #2E2E2E;
}

QTableWidget::item:selected {
    background-color: #18324F;
    color: #FFFFFF;
}

QHeaderView::section {
    background-color: #1E1E1E;
    color: #CCCCCC;
    font-weight: bold;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #333333;
}
"""
