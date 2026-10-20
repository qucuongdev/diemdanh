"""Timezone, display and role rules shared by every view."""

from datetime import datetime, timedelta, timezone

LOCAL_TZ = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")
ROLES = {"admin": "Chủ chuỗi", "storemanager": "Quản lý chi nhánh", "staff": "Dược sĩ"}


def local_now():
    return datetime.now(LOCAL_TZ)


def parse_timestamp(value):
    if not value:
        return None
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return (result if result.tzinfo else result.replace(tzinfo=LOCAL_TZ)).astimezone(LOCAL_TZ)


def display_time(value):
    try:
        parsed = parse_timestamp(value)
        return parsed.strftime("%H:%M") if parsed else "—"
    except (TypeError, ValueError):
        return "—"


def timestamp_tooltip(value):
    """Keep the date and second-level precision available behind the minute display."""
    try:
        parsed = parse_timestamp(value)
        return parsed.strftime("%d/%m/%Y %H:%M:%S") + " · Giờ Việt Nam" if parsed else "—"
    except (TypeError, ValueError):
        return "—"


def display_duration(minutes):
    """Format whole, nonnegative server minutes without wrapping at 24 hours."""
    if type(minutes) is not int or minutes < 0:
        return "—"
    hours, remainder = divmod(minutes, 60)
    return f"{hours:02d}:{remainder:02d}"


def attendance_notes(record, *, include_unit=True):
    values = []
    if record.get("is_late"):
        values.append(f"Muộn {display_duration(record.get('late_minutes'))}")
    if record.get("is_early_leave"):
        values.append(f"Về sớm {display_duration(record.get('early_minutes'))}")
    result = " · ".join(values)
    return f"{result} (giờ:phút)" if result and include_unit else result


def first_attendance(schedule):
    value = schedule.get("attendance") or {}
    return value[0] if isinstance(value, list) and value else (value if isinstance(value, dict) else {})


def validate_profile(profile):
    if not profile or not profile.get("id") or profile.get("role") not in ROLES:
        raise ValueError("Hồ sơ tài khoản không hợp lệ.")
    if profile.get("is_active") is not True:
        raise ValueError("Tài khoản đã bị vô hiệu hóa.")
    if profile["role"] != "admin" and not profile.get("branch_id"):
        raise ValueError("Tài khoản chưa được phân chi nhánh. Liên hệ quản trị viên.")
    return profile


def safe_excel_text(value):
    text = str(value or "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
