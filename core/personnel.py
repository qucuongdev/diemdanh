"""Personnel validation and payroll presentation, independent of Qt/network."""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from core.ui_messages import UserInputError


PERSONAL_FIELDS = [
    ("employee_code", "Mã nhân viên"), ("birth_date", "Ngày sinh YYYY-MM-DD"),
    ("gender", "Giới tính"), ("contact_email", "Email liên hệ"),
    ("identity_number", "Số CCCD/CMND"), ("identity_date", "Ngày cấp YYYY-MM-DD"),
    ("identity_place", "Nơi cấp"), ("bank_account", "Số tài khoản ngân hàng"),
    ("bank_name", "Ngân hàng"), ("bank_holder", "Chủ tài khoản"),
    ("hometown", "Quê quán"), ("permanent_address", "Địa chỉ thường trú"),
    ("current_address", "Địa chỉ hiện tại"), ("job_title", "Chức danh"),
    ("hire_date", "Ngày vào làm YYYY-MM-DD"), ("end_date", "Ngày nghỉ việc YYYY-MM-DD"),
    ("emergency_name", "Liên hệ khẩn cấp"), ("emergency_relation", "Quan hệ"),
    ("emergency_phone", "SĐT khẩn cấp"), ("birthday_notice_days", "Nhắc sinh nhật trước (ngày)"),
]
TERM_FIELDS = [
    ("effective_month", "Áp dụng từ YYYY-MM-01"), ("monthly_salary", "Lương tháng (đồng)"),
    ("paid_rest_days", "Ngày nghỉ hưởng lương/tháng"), ("daily_minutes", "Công chuẩn/ngày (hh:mm hoặc N phút)"),
    ("attendance_bonus", "Thưởng chuyên cần (đồng)"),
    ("allowed_late_count", "Số lần muộn tối đa vẫn được thưởng"),
]
DAY_KINDS = {
    "regular": "Công thường", "rest": "Nghỉ định mức", "paid_leave": "Phép hưởng lương",
    "unpaid_leave": "Nghỉ không lương", "extra_work": "Làm thêm ngày nghỉ", "absent": "Vắng không phép",
    "outside": "Ngoài thời gian làm việc",
}


def display_money(value):
    if value is None:
        return "—"
    amount = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{amount:,.0f}".replace(",", ".") + " đ"


def validate_personal(values, today):
    for key in ("birth_date", "identity_date", "hire_date", "end_date"):
        if values.get(key):
            try:
                parsed = date.fromisoformat(values[key])
                if key == "birth_date" and not date(1900, 1, 1) <= parsed <= today:
                    raise ValueError()
            except ValueError:
                raise UserInputError("Ngày không hợp lệ; nhập YYYY-MM-DD hoặc để trống.") from None
    if values.get("hire_date") and values.get("end_date") and values["end_date"] < values["hire_date"]:
        raise UserInputError("Ngày nghỉ việc phải từ ngày vào làm trở đi.")
    identity = values.get("identity_number", "")
    if identity and (not identity.isascii() or not identity.isdigit() or len(identity) not in (9, 12)):
        raise UserInputError("CCCD/CMND cần 9 hoặc 12 chữ số.")
    try:
        days = int(values.get("birthday_notice_days", "7"))
        if not 0 <= days <= 60:
            raise ValueError()
    except ValueError:
        raise UserInputError("Số ngày nhắc sinh nhật cần từ 0 đến 60.") from None
    if any(len(value) > 1000 for value in values.values()):
        raise UserInputError("Mỗi trường thông tin tối đa 1.000 ký tự.")
    return values


def validate_terms(values):
    try:
        month = date.fromisoformat(values["effective_month"])
        if month.day != 1:
            raise ValueError()
        result = {}
        for key, maximum in [("monthly_salary", 999999999999), ("paid_rest_days", 27),
                             ("daily_minutes", 1440), ("attendance_bonus", 999999999999),
                             ("allowed_late_count", 1000)]:
            value = values[key]
            if key == "daily_minutes":
                if ":" in value:
                    hours, minutes = value.split(":")
                    if not hours.isdigit() or not minutes.isdigit() or not 0 <= int(minutes) < 60:
                        raise ValueError()
                    value = str(int(hours) * 60 + int(minutes))
                elif value.endswith(" phút"):
                    value = value[:-5]
            number = Decimal(value)
            if not number.is_finite() or number != number.to_integral_value() or not 0 <= number <= maximum:
                raise ValueError()
            result[key] = int(number)
        if result["daily_minutes"] == 0:
            raise ValueError()
    except (KeyError, ValueError, InvalidOperation):
        raise UserInputError("Nhập ngày đầu tháng và số nguyên hợp lệ; giờ chuẩn/ngày phải lớn hơn 0.") from None
    return month.isoformat(), result
