"""Timezone, display and role rules shared by every view."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import ceil
from core.ui_messages import UserInputError

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
    """Show durations below one hour in minutes, otherwise as unbounded HH:mm."""
    if type(minutes) is not int or minutes < 0:
        return "—"
    if minutes < 60:
        return f"{minutes} phút"
    hours, remainder = divmod(minutes, 60)
    return f"{hours:02d}:{remainder:02d}"


def attendance_notes(record):
    values = []
    if record.get("is_late"):
        values.append(f"Muộn {display_duration(record.get('late_minutes'))}")
    if record.get("is_early_leave"):
        values.append(f"Về sớm {display_duration(record.get('early_minutes'))}")
    return " · ".join(values)


def first_attendance(schedule):
    value = schedule.get("attendance") or {}
    return value[0] if isinstance(value, list) and value else (value if isinstance(value, dict) else {})


@dataclass(frozen=True)
class WorkCredit:
    minutes: int | None
    missing_minutes: int | None
    status: str


def attendance_work_credit(record):
    """Credit only the overlap with the assigned shift; never infer missing timestamps."""
    if not record.get("check_in"):
        return WorkCredit(None, None, "Chưa check-in")
    if not record.get("check_out"):
        return WorkCredit(None, None, "Chưa check-out")
    try:
        schedule = record.get("schedules") or {}
        shift = schedule.get("shifts") or {}
        work_date = date.fromisoformat(str(schedule["work_date"]))
        start = datetime.combine(work_date, time.fromisoformat(shift["start_time"]), LOCAL_TZ)
        end = datetime.combine(work_date, time.fromisoformat(shift["end_time"]), LOCAL_TZ)
        if end <= start:
            end += timedelta(days=1)
        check_in = parse_timestamp(record["check_in"])
        check_out = parse_timestamp(record["check_out"])
        if check_out < check_in:
            raise ValueError("Reversed attendance timestamps")
        planned_seconds = (end - start).total_seconds()
        worked_seconds = max(0, (min(end, check_out) - max(start, check_in)).total_seconds())
        minutes = int(worked_seconds // 60)
        missing = ceil((planned_seconds - worked_seconds) / 60)
        return WorkCredit(minutes, missing, "Done" if missing == 0 else f"Thiếu {display_duration(missing)}")
    except (KeyError, TypeError, ValueError, OverflowError):
        return WorkCredit(None, None, "Không đủ dữ liệu")


def validate_profile(profile):
    if not profile or not profile.get("id") or profile.get("role") not in ROLES:
        raise UserInputError("Hồ sơ tài khoản không hợp lệ.")
    if profile.get("is_active") is not True:
        raise UserInputError("Tài khoản đã bị vô hiệu hóa.")
    if profile["role"] != "admin" and not profile.get("branch_id"):
        raise UserInputError("Tài khoản chưa được phân chi nhánh. Liên hệ quản trị viên.")
    return profile


def safe_excel_text(value):
    text = str(value or "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
