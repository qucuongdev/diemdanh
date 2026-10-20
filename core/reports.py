"""Report transformations and filesystem export; no Qt dependency."""

import os
import tempfile
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill
from core.domain import first_attendance, display_time, safe_excel_text


def summarize(schedules):
    staff = {}
    for schedule in schedules:
        profile = schedule.get("profiles") or {}
        key = profile.get("id") or schedule.get("user_id")
        item = staff.setdefault(
            key,
            {
                "name": profile.get("full_name", "Không rõ"),
                "total": 0,
                "ontime": 0,
                "late": 0,
                "late_minutes": 0,
                "leave": 0,
                "unrecorded": 0,
            },
        )
        item["total"] += 1
        if schedule.get("status") == "leave":
            item["leave"] += 1
            continue
        attendance = first_attendance(schedule)
        if not attendance:
            item["unrecorded"] += 1
        elif attendance.get("is_late"):
            item["late"] += 1
            item["late_minutes"] += attendance.get("late_minutes") or 0
        else:
            item["ontime"] += 1
    return sorted(staff.values(), key=lambda item: item["name"].casefold())


def export_attendance(path, schedules, title):
    path = Path(path)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Chấm công"
    sheet.append([safe_excel_text(title)])
    sheet.append(["STT", "Họ tên", "Ngày", "Ca", "Vào ca", "Tan ca", "Phút trễ", "Trạng thái"])
    for number, schedule in enumerate(schedules, 1):
        attendance = first_attendance(schedule)
        sheet.append(
            [
                number,
                safe_excel_text((schedule.get("profiles") or {}).get("full_name")),
                safe_excel_text(schedule.get("work_date")),
                safe_excel_text((schedule.get("shifts") or {}).get("name")),
                display_time(attendance.get("check_in")),
                display_time(attendance.get("check_out")),
                attendance.get("late_minutes") or 0,
                {
                    "leave": "Nghỉ phép",
                    "scheduled": "Đã xếp ca",
                    "completed": "Hoàn thành",
                    "absent": "Vắng",
                }.get(schedule.get("status"), "Không rõ"),
            ]
        )
    for cell in sheet[2]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2563EB")
    for column, width in {"A": 8, "B": 32, "C": 16, "D": 24, "E": 16, "F": 16, "G": 14, "H": 20}.items():
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = "A3"
    sheet.auto_filter.ref = f"A2:H{sheet.max_row}"
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
