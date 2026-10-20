import os
import sys
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Mock SupabaseService to test completely offline and instantly
from core.supabase_service import SupabaseService
SupabaseService.get_today_schedule = MagicMock(return_value={"success": True, "schedules": []})
SupabaseService.get_branches = MagicMock(return_value=[{"id": "b1", "name": "Chi nhánh 1"}])
SupabaseService.get_staff_list = MagicMock(return_value=[{"id": "s1", "full_name": "Nhân viên 1", "role": "staff"}])
SupabaseService.get_shifts = MagicMock(return_value=[{"id": "sh1", "name": "Ca sáng", "start_time": "08:00:00", "end_time": "16:00:00"}])
SupabaseService.get_schedules_range = MagicMock(return_value=[])
SupabaseService.get_pending_leave_requests = MagicMock(return_value=[])
SupabaseService.get_pending_proof_attendances = MagicMock(return_value=[])
SupabaseService.get_monthly_kpi_summary = MagicMock(return_value=[])
SupabaseService.get_registered_devices = MagicMock(return_value=[])

from PySide6.QtWidgets import QApplication
from main_qt import MainWindow

def test_full_qt_lifecycle():
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    # 1. Initial State: Login View
    assert window.root_stack.currentIndex() == 0
    assert window.login_view is not None

    # 2. Simulate Admin Login
    admin_profile = {
        "id": "mock-admin-id",
        "full_name": "Quản Trị Viên",
        "role": "admin",
        "branch_id": "mock-branch-1",
        "branches": {"name": "Tổng bộ"}
    }
    window.on_login_success(admin_profile)
    assert window.root_stack.currentIndex() == 1
    assert window.main_app_widget.role_badge.text() == "👑 CHỦ CHUỖI"

    # Admin should have 5 nav buttons
    assert len(window.main_app_widget.nav_buttons) == 5
    assert set(window.main_app_widget.nav_buttons.keys()) == {
        "attendance", "schedule", "approval", "reports", "settings"
    }

    # 3. Test switching through all 5 views
    for view_key in ["attendance", "schedule", "approval", "reports", "settings"]:
        window.main_app_widget.show_view(view_key)
        assert view_key in window.main_app_widget.views
        current_w = window.main_app_widget.content_stack.currentWidget()
        assert current_w == window.main_app_widget.views[view_key]
        assert window.main_app_widget.active_nav_key == view_key

    # 4. Test Staff Login
    staff_profile = {
        "id": "mock-staff-id",
        "full_name": "Dược Sĩ Test",
        "role": "staff",
        "branch_id": "mock-branch-2",
        "branches": {"name": "Chi nhánh 2"}
    }
    window.on_login_success(staff_profile)
    assert window.main_app_widget.role_badge.text() == "💊 DƯỢC SĨ"

    # Staff should only have 2 nav buttons
    assert len(window.main_app_widget.nav_buttons) == 2
    assert set(window.main_app_widget.nav_buttons.keys()) == {"attendance", "schedule"}

    # 5. Test Logout
    window.main_app_widget.handle_logout()
    assert window.root_stack.currentIndex() == 0
    assert window.current_profile is None

    app.processEvents()
    from core.qt_worker import QtWorker
    QtWorker.wait_all(3000)

    print("\n>>> ALL PYSIDE6 INTEGRATION & LIFECYCLE TESTS PASSED! <<<")
    sys.exit(0)

if __name__ == "__main__":
    test_full_qt_lifecycle()
