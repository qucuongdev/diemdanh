# Trạng thái bản Qt — 2026-10-21

Ứng dụng chỉ dùng PySide6 và khởi chạy duy nhất qua `main.py`. Tài liệu này thay thế kế hoạch CustomTkinter cũ.

Nhật ký bàn giao và thứ tự công việc cho chat tiếp theo: [WORKLOG.md](WORKLOG.md).

## Đã triển khai trong mã

- Đăng nhập Supabase, kiểm tra hồ sơ/vai trò/chi nhánh và quyền máy quầy.
- Kiểm tra backend tương thích; phân biệt thiếu migration, thiếu quyền và lỗi kết nối mà không hiển thị lỗi máy chủ thô.
- Check-in/check-out qua RPC dùng giờ PostgreSQL; hiển thị nhiều ca và check-out ca đêm đã bắt đầu hôm trước.
- App 1.0.0 hiển thị giờ và thời lượng theo hh:mm. Phút gốc vẫn dùng để tính tổng; Excel dùng thời lượng số với định dạng [h]:mm, không quay về 0 sau 24 giờ.
- Giao diện sáng/tối dùng chung bảng màu, đổi ngay tại đăng nhập hoặc sidebar và lưu lựa chọn cho lần mở tiếp theo.
- Lịch tháng, xếp/xóa ca chưa chấm công, xin nghỉ và duyệt/từ chối yêu cầu.
- Ảnh giải trình được nén ở tác vụ nền, lưu riêng tư và xem bằng URL có hạn.
- Lịch sử phân trang bằng Qt model/view; báo cáo đọc hết các trang và xuất Excel ở tác vụ nền.
- Quản trị chi nhánh, ca, nhân viên và máy quầy cho chủ chuỗi.
- Bảo vệ tác vụ theo vòng đời widget; bỏ kết quả cũ khi yêu cầu mới thay thế; chống gửi trùng thao tác ghi.
- Migration 04 bổ sung quyền bảng ca còn thiếu, chặn sửa giờ ca đã có chấm công, giới hạn hồ sơ admin và bảo đảm tạo Auth/identity/profile nguyên tử.

## Cách chạy

Xem README.md để chọn lệnh Git Bash hoặc PowerShell. Dùng `python main.py` sau khi cài thư viện vào đúng Python, hoặc kích hoạt `.venv` rồi chạy lệnh này.

## Còn cần thực hiện ở môi trường triển khai

- Đối chiếu preflight.sql và lịch sử migration; áp dụng đúng thứ tự theo DEPLOYMENT.md. App 1.0.0 yêu cầu backend 3.
- Kiểm tra riêng Supabase Auth, Storage, RLS và RPC bằng tài khoản admin, quản lý và dược sĩ trên dự án thử nghiệm.
- Kiểm tra luồng ca đêm, yêu cầu đồng thời và báo cáo lớn với dữ liệu thử đã biết kết quả.
- Đối chiếu tài khoản cũ thiếu identity và các xung đột dữ liệu trước migration. Không tự sửa dữ liệu thật từ kiểm thử.

## Phạm vi chưa triển khai

- Duyệt ảnh giải trình chưa tự điều chỉnh giờ chấm công. Cần thiết kế RPC điều chỉnh có nhật ký kiểm toán trước khi bổ sung.
- Yêu cầu đổi ca chưa tự phân người thay.
- Chưa có công thức lương hoặc gói cài đặt `.exe`.
- Device UUID là định danh do client cung cấp, không bảo đảm chống giả mạo tuyệt đối.

## Xác minh

Kết quả cục bộ và phiên bản thư viện được ghi trong AGENTS.md. Kiểm thử ngoại tuyến không xác nhận production hoặc database đã được cập nhật.
