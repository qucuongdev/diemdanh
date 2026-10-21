"""Atomic payroll export; callers fetch every page and invoke this in a worker."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import os
import tempfile
import openpyxl
from openpyxl.styles import Font
from core.domain import safe_excel_text
from core.ui_messages import public_payroll_warning


def export_payroll(path, records, month):
    path = Path(path)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Bảng lương"
    sheet.append([f"Bảng lương {month[:7]} · Chỉ các dòng Đã chốt là kết quả cố định"])
    sheet.append(["Họ tên", "Chi nhánh", "Lương tháng", "Công chuẩn", "Công thường", "Phép hưởng lương",
                  "Làm thêm", "Thiếu công", "Số lần muộn", "Tiền trừ", "Tiền làm thêm", "Chuyên cần",
                  "Thực nhận", "Trạng thái", "Cảnh báo"])
    for index, record in enumerate(records, 3):
        def money(key, record=record):
            value = record.get(key)
            return int(Decimal(str(value))) if value is not None else None

        durations = [record.get(key) for key in ("expected_minutes", "regular_minutes", "paid_leave_minutes",
                                                "extra_minutes", "missing_minutes")]
        sheet.append([
            safe_excel_text(record.get("full_name")), safe_excel_text(record.get("branch_name")),
            money("monthly_salary"),
            *(timedelta(minutes=value) if type(value) is int and value >= 0 else None for value in durations),
            record.get("late_count"), money("deduction"), money("extra_pay"), money("bonus"), money("net_salary"),
            "Đã chốt" if record.get("finalized") else "Tạm tính",
            safe_excel_text("; ".join(public_payroll_warning(w) for w in (record.get("warnings") or []))),
        ])
        for column, minutes in enumerate(durations, 4):
            sheet.cell(index, column).number_format = '[m]" phút"' if type(minutes) is int and 0 <= minutes < 60 else '[hh]:mm'
        for column in (3, 10, 11, 12, 13):
            sheet.cell(index, column).number_format = '#,##0" đ"'
    for cell in sheet[2]:
        cell.font = Font(bold=True)
    for column in range(1, 16):
        sheet.column_dimensions[openpyxl.utils.get_column_letter(column)].width = 23
    sheet.column_dimensions["A"].width = 30
    sheet.column_dimensions["O"].width = 60
    sheet.freeze_panes = "C3"
    sheet.auto_filter.ref = f"A2:O{sheet.max_row}"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".xlsx", delete=False) as stream:
            temporary = stream.name
        workbook.save(temporary)
        os.replace(temporary, path)
    finally:
        workbook.close()
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return str(path)
