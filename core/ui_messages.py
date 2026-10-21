"""Public UI messages. Never render infrastructure diagnostics or raw exceptions."""

from datetime import date

SYSTEM_UNAVAILABLE = "Không thể hoàn tất thao tác lúc này. Vui lòng thử lại hoặc liên hệ quản trị viên."
CONNECTION_UNAVAILABLE = "Không thể kết nối. Vui lòng kiểm tra mạng và thử lại."


class UserInputError(ValueError):
    """Expected validation failure with fixed, code-owned user-facing wording.

    Never construct this with server text, exception text, credentials or user data.
    """


# Explicit public vocabulary: arbitrary strings from a future service cannot pass
# the final UI boundary merely because they look like a human-readable message.
PUBLIC_ERRORS = frozenset({
    SYSTEM_UNAVAILABLE, CONNECTION_UNAVAILABLE,
    "Bạn không có quyền duyệt yêu cầu.", "Bạn không có quyền thực hiện thao tác này.",
    "Chỉ admin được xem nhân sự và bảng lương.", "Chỉ chủ chuỗi có quyền quản trị hệ thống.",
    "Chỉ admin được xem hoặc thay đổi nhân sự và lương.",
    "Hồ sơ tài khoản không hợp lệ.", "Không tìm thấy hồ sơ người dùng!",
    "Tài khoản đã bị vô hiệu hóa.", "Tài khoản của bạn đã bị vô hiệu hóa. Vui lòng liên hệ Quản lý!",
    "Tài khoản chưa được phân chi nhánh. Liên hệ quản trị viên.",
    "Tài khoản chưa có chi nhánh để gửi giải trình.", "Chưa đăng nhập!",
    "Nhập tài khoản và mật khẩu để tiếp tục.", "Sai tài khoản hoặc mật khẩu đăng nhập!",
    "Đăng nhập thất bại.", "Đăng nhập thất bại, vui lòng kiểm tra lại tài khoản và mật khẩu!",
    "Máy này chưa được cấp phép tại chi nhánh của bạn.", "Thiết bị chưa được cấp phép.",
    "Thiết bị máy quầy này chưa được cấp phép điểm danh tại chi nhánh!",
    "Ca này đã được ghi nhận tan ca. Hãy làm mới dữ liệu.",
    "Ca làm việc này đã được Check-in trước đó!", "Chưa đến giờ tan ca theo giờ máy chủ. Vui lòng chờ hết ca.",
    "Không thay đổi tài khoản chủ chuỗi qua màn hình này.",
    "Tài khoản Quản trị viên tối cao được bảo vệ, không thể thay đổi quyền hoặc xóa!",
    "Chi nhánh này đã có Cửa hàng trưởng! Mỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý.",
    "Dữ liệu nhập vào bị trùng lặp với bản ghi đã tồn tại trong hệ thống!",
    "Tên đăng nhập hoặc email đã được sử dụng. Vui lòng chọn tên khác.",
    "Thông tin bị trùng. Kiểm tra mã nhân viên hoặc kỳ lương.",
    "Dữ liệu này đang liên kết với các bản ghi khác (nhân sự, lịch hoặc thiết bị). Vui lòng xử lý các dữ liệu liên quan trước khi xóa!",
    "Chi nhánh này đang có nhân sự, ca làm hoặc máy tính liên kết. Vui lòng chuyển các mục đó trước khi xóa!",
    "Ca làm việc này đã được phân công trong lịch làm việc, không thể xóa!",
    "Không thể xóa ca đã có dữ liệu chấm công.", "Không thể xóa lịch làm việc này.",
    "Chọn chi nhánh hợp lệ để xem báo cáo.", "Chọn ngày có ca của bạn chưa chấm công để xin nghỉ.",
    "Cần chi nhánh và nội dung giải trình hợp lệ.", "Ảnh sau nén vượt quá 500 KB. Chọn ảnh nhỏ hơn.",
    "Thông tin phê duyệt không hợp lệ.", "Yêu cầu đã được xử lý hoặc bạn không có quyền duyệt.",
    "Ngày không hợp lệ. Dùng định dạng YYYY-MM-DD.",
    "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!",
    "Không thể kết nối đến máy chủ. Vui lòng kiểm tra đường truyền mạng!",
    "Không thể mở ảnh minh chứng.", "Không thể thực hiện Check-in. Vui lòng thử lại!",
    "Không thể thực hiện Check-out. Vui lòng thử lại!", "Không thể tải lên ảnh minh chứng. Vui lòng thử lại!",
    "Không thể gửi đơn xin nghỉ. Vui lòng thử lại!", "Không thể cập nhật trạng thái đơn.",
    "Không thể cập nhật minh chứng.", "Không thể cập nhật thông tin thiết bị.",
    "Không thể thay đổi trạng thái thiết bị.", "Không thể đăng ký máy tính này vào hệ thống.",
    "Không thể xóa thiết bị.", "Không thể tạo ca làm việc mới.", "Không thể cập nhật ca làm việc.",
    "Không thể tạo chi nhánh mới.", "Không thể cập nhật chi nhánh.", "Không thể đọc dữ liệu lịch ca hôm nay.",
    "Không thể đọc hồ sơ tài khoản.", "Không thể xếp ca làm việc. Vui lòng kiểm tra lại thông tin!",
    "Dữ liệu đã thay đổi. Đóng cửa sổ, tải lại rồi thực hiện lại.",
    "Kỳ lương đã chốt; không thể sửa chế độ hoặc phân loại ngày của kỳ này.",
    "Chưa hết tháng hoặc còn cảnh báo cần xử lý trước khi chốt.",
    "Thông tin không hợp lệ. Kiểm tra ngày, số tiền và các trường bắt buộc.",
    "CCCD/CMND cần 9 hoặc 12 chữ số.", "Ngày không hợp lệ; nhập YYYY-MM-DD hoặc để trống.",
    "Ngày nghỉ việc phải từ ngày vào làm trở đi.", "Số ngày nhắc sinh nhật cần từ 0 đến 60.",
    "Mỗi trường thông tin tối đa 1.000 ký tự.",
    "Nhập ngày đầu tháng và số nguyên hợp lệ; giờ chuẩn/ngày phải lớn hơn 0.",
})

PAYROLL_WARNINGS = {
    text: text for text in (
        "Chưa cấu hình lương", "Không có công chuẩn trong kỳ",
        "Công được xếp/phân loại chưa khớp công chuẩn",
        "Số ngày nghỉ/làm thêm vượt định mức nghỉ hưởng lương", "Công hưởng lương vượt công chuẩn",
        "Ca chồng nhau", "Ca hoàn thành thiếu chấm công", "Ca chưa chấm công: cần xác nhận vắng/nghỉ",
        "Chưa check-out", "Chấm công không khớp ca", "Dữ liệu ngoài thời gian làm việc",
        "Tổng ca vượt giờ chuẩn/ngày", "Cần phân loại nghỉ hưởng lương/không lương",
        "Có chấm công trên ngày nghỉ: cần phân loại lại",
    )
}
PAYROLL_WARNINGS["Phút muộn không khớp timestamp"] = "Thời gian chấm công và số phút muộn chưa khớp."


def public_error_message(value):
    if isinstance(value, UserInputError):
        value = str(value)
    return value if isinstance(value, str) and value in PUBLIC_ERRORS else SYSTEM_UNAVAILABLE


def public_payroll_warning(value):
    """Only known payroll business warnings, optionally prefixed by an ISO date."""
    if value == "":
        return ""
    if not isinstance(value, str) or len(value) > 4096:
        return SYSTEM_UNAVAILABLE
    prefix = ""
    if value[10:12] == ": ":
        try:
            prefix = date.fromisoformat(value[:10]).isoformat() + ": "
        except ValueError:
            return SYSTEM_UNAVAILABLE
        value = value[12:]
    parts = value.split(" · ")
    if all(part in PAYROLL_WARNINGS for part in parts):
        return prefix + " · ".join(PAYROLL_WARNINGS[part] for part in parts)
    return SYSTEM_UNAVAILABLE


def public_mutation_result(data):
    """Keep RPC result fields, but never forward server-provided message strings."""
    if not isinstance(data, dict) or data.get("success") is not True:
        return {"success": False, "message": SYSTEM_UNAVAILABLE}
    return {**data, "message": "Đã hoàn tất thao tác."}
