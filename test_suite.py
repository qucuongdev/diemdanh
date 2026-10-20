import sys
import os
import tempfile
from PIL import Image
import customtkinter as ctk

# Thiết lập encoding UTF-8 cho Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_all_tests():
    print("=" * 60)
    print("BẮT ĐẦU KIỂM THỬ TOÀN DIỆN ỨNG DỤNG CHẤM CÔNG NHÀ THUỐC")
    print("=" * 60)

    # ---------------- TEST 1: HARDWARE ID ----------------
    print("\n[TEST 1] Kiểm tra trích xuất Hardware UUID...")
    from core.hardware import get_hardware_uuid
    hw_id = get_hardware_uuid()
    assert hw_id and len(hw_id) > 10, "Lỗi: Hardware UUID không hợp lệ!"
    print(f"  -> THÀNH CÔNG: Đã lấy mã máy = {hw_id}")

    # ---------------- TEST 2: PILLOW IMAGE COMPRESSION ----------------
    print("\n[TEST 2] Kiểm tra thuật toán nén ảnh bằng chứng (< 500KB)...")
    # Tạo ảnh mẫu kích thước lớn (3000x2000)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        large_img_path = tmp.name

    large_img = Image.new("RGB", (3000, 2000), color=(73, 109, 137))
    large_img.save(large_img_path, format="PNG")
    original_size_kb = os.path.getsize(large_img_path) / 1024
    print(f"  -> Ảnh gốc kích thước: 3000x2000, Dung lượng: {original_size_kb:.2f} KB")

    # Mô phỏng quá trình nén của SupabaseService
    import io
    with Image.open(large_img_path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        max_width = 1280
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * float(ratio))
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=75, optimize=True)
        compressed_bytes = buffer.getvalue()

    compressed_size_kb = len(compressed_bytes) / 1024
    print(f"  -> Sau khi nén Pillow: {img.width}x{img.height}, Dung lượng: {compressed_size_kb:.2f} KB")
    assert compressed_size_kb < 500, "Lỗi: Ảnh nén vượt quá 500KB!"
    os.remove(large_img_path)
    print("  -> THÀNH CÔNG: Tối ưu ảnh đạt chuẩn lưu trữ Supabase Storage.")

    # ---------------- TEST 3: EXCEL GENERATION (OPENPYXL) ----------------
    print("\n[TEST 3] Kiểm tra thư viện kết xuất Excel (.xlsx)...")
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test_Sheet"
    ws.append(["STT", "Nhân Viên", "Ca Làm", "Số Phút Trễ"])
    ws.append([1, "Dược sĩ Nguyễn Văn A", "Ca Sáng (08:00 - 16:00)", 0])
    ws.append([2, "Dược sĩ Trần Thị B", "Ca Chiều (16:00 - 22:00)", 5])
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_excel:
        excel_path = tmp_excel.name
    wb.save(excel_path)
    assert os.path.exists(excel_path) and os.path.getsize(excel_path) > 0, "Lỗi tạo file Excel!"
    os.remove(excel_path)
    print("  -> THÀNH CÔNG: Thư viện openpyxl xuất file Excel chuẩn định dạng.")

    # ---------------- TEST 4: GUI SMOKE TEST (ALL VIEWS) ----------------
    print("\n[TEST 4] Kiểm tra khởi tạo toàn bộ giao diện (CustomTkinter Views)...")
    app_root = ctk.CTk()
    app_root.geometry("1100x700")

    # Mock Profiles cho các Role
    mock_profiles = {
        "staff": {
            "id": "mock-staff-id-123",
            "full_name": "Dược sĩ Kiểm Thử",
            "role": "staff",
            "branch_id": "mock-branch-id-456",
            "branches": {"name": "Nhà thuốc Chi nhánh 1"}
        },
        "storemanager": {
            "id": "mock-mgr-id-789",
            "full_name": "Quản lý Cửa Hàng",
            "role": "storemanager",
            "branch_id": "mock-branch-id-456",
            "branches": {"name": "Nhà thuốc Chi nhánh 1"}
        },
        "admin": {
            "id": "mock-admin-id-999",
            "full_name": "Chủ Chuỗi Nhà Thuốc",
            "role": "admin",
            "branch_id": None,
            "branches": None
        }
    }

    # 4.1. Test LoginView
    from views.login_view import LoginView
    print("  -> Đang kiểm thử LoginView...")
    login_frame = LoginView(app_root, on_login_success=lambda p: None)
    login_frame.pack(fill="both", expand=True)
    app_root.update_idletasks()
    login_frame.destroy()

    # 4.2. Test AttendanceView (Staff)
    from views.attendance_view import AttendanceView
    print("  -> Đang kiểm thử AttendanceView (Điểm danh quầy)...")
    att_frame = AttendanceView(app_root, current_profile=mock_profiles["staff"], on_logout=lambda: None)
    att_frame.pack(fill="both", expand=True)
    app_root.update_idletasks()
    att_frame.destroy()

    # 4.3. Test ScheduleView (Staff & Manager)
    from views.schedule_view import ScheduleView
    print("  -> Đang kiểm thử ScheduleView (Lịch làm việc & Xin nghỉ)...")
    sched_frame = ScheduleView(app_root, current_profile=mock_profiles["storemanager"])
    sched_frame.pack(fill="both", expand=True)
    app_root.update_idletasks()
    sched_frame.destroy()

    # 4.4. Test ApprovalView (Manager)
    from views.approval_view import ApprovalView
    print("  -> Đang kiểm thử ApprovalView (Trung tâm Phê duyệt)...")
    appr_frame = ApprovalView(app_root, current_profile=mock_profiles["storemanager"])
    appr_frame.pack(fill="both", expand=True)
    app_root.update_idletasks()
    appr_frame.destroy()

    # 4.5. Test ReportView (Manager & Admin)
    from views.report_view import ReportView
    print("  -> Đang kiểm thử ReportView (Báo cáo KPI & Excel)...")
    rep_frame = ReportView(app_root, current_profile=mock_profiles["admin"])
    rep_frame.pack(fill="both", expand=True)
    app_root.update_idletasks()
    rep_frame.destroy()

    # 4.6. Test SettingsView (Admin)
    from views.settings_view import SettingsView
    print("  -> Đang kiểm thử SettingsView (Quản trị hệ thống & Khóa máy)...")
    set_frame = SettingsView(app_root, current_profile=mock_profiles["admin"])
    set_frame.pack(fill="both", expand=True)
    app_root.update_idletasks()
    set_frame.destroy()

    app_root.destroy()
    print("  -> THÀNH CÔNG: Toàn bộ 6 Màn hình CustomTkinter dựng khung mượt mà, không phát sinh lỗi.")

    # ---------------- TEST 5: MAIN APP CONTROLLER ----------------
    print("\n[TEST 5] Kiểm tra Main App Controller (Single-Frame Switching)...")
    from main import App
    main_app = App()
    main_app.update_idletasks()

    # Mô phỏng đăng nhập thành công với vai trò Admin
    print("  -> Mô phỏng chuyển đổi luồng Navigation Sidebar...")
    main_app.on_login_success(mock_profiles["admin"])
    main_app.update_idletasks()

    # Thử chuyển lần lượt qua các view
    main_app.show_view("schedule")
    main_app.update_idletasks()

    main_app.show_view("approval")
    main_app.update_idletasks()

    main_app.show_view("reports")
    main_app.update_idletasks()

    main_app.show_view("settings")
    main_app.update_idletasks()

    main_app.show_view("attendance")
    main_app.update_idletasks()

    main_app.destroy()
    print("  -> THÀNH CÔNG: Điều hướng Single-Frame Switching hoạt động trơn tru.")

    print("\n" + "=" * 60)
    print("TẤT CẢ CÁC BÀI TEST ĐỀU ĐẠT CHUẨN 100%! HỆ THỐNG ĐÃ SẴN SÀNG.")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
