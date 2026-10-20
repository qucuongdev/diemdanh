import io
import os
import uuid
from datetime import datetime, date, timedelta
from PIL import Image
from supabase import create_client, Client
from core.config import SUPABASE_URL, SUPABASE_KEY

class SupabaseService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseService, cls).__new__(cls)
            cls._instance.client: Client = None
            cls._instance.current_user = None
            cls._instance.current_profile = None
            cls._instance._cache = {
                "branches": None,
                "staffs": None,
                "shifts": None
            }
            cls._instance.init_client()
        return cls._instance

    def init_client(self):
        if SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL != "https://your-project-id.supabase.co":
            try:
                self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
            except Exception as e:
                print(f"[LỖI] Khởi tạo Supabase client thất bại: {e}")
                self.client = None
        else:
            self.client = None

    def is_configured(self) -> bool:
        return self.client is not None

    def _sanitize_error(self, err: Exception, fallback: str = "Thao tác không thành công. Vui lòng kiểm tra kết nối mạng và thử lại!") -> str:
        """Bảo mật: Ghi log nội bộ cho Sysadmin/Dev, tuyệt đối KHÔNG để lộ chi tiết database, mã lỗi hay kiến trúc máy chủ ra ngoài giao diện"""
        err_str = str(err)
        print(f"[SECURITY/LOG] Lỗi máy chủ: {err_str}")

        if "Chi nhánh này đã có Cửa hàng trưởng" in err_str:
            return "Chi nhánh này đã có Cửa hàng trưởng! Mỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý."
        if "đã tồn tại" in err_str or "duplicate key" in err_str or "unique constraint" in err_str:
            return "Dữ liệu nhập vào bị trùng lặp với bản ghi đã tồn tại trong hệ thống!"
        if "Không thể xóa tài khoản Admin" in err_str or "Không thể hạ quyền" in err_str:
            return "Tài khoản Quản trị viên tối cao được bảo vệ, không thể thay đổi quyền hoặc xóa!"
        if "Thiết bị này không hợp lệ" in err_str:
            return "Thiết bị máy quầy này chưa được cấp phép điểm danh tại chi nhánh!"
        if "Ca làm việc này đã được Check-in" in err_str:
            return "Ca làm việc này đã được Check-in trước đó!"
        if "Invalid login credentials" in err_str:
            return "Sai tài khoản hoặc mật khẩu đăng nhập!"
        if "foreign key constraint" in err_str:
            return "Dữ liệu này đang liên kết với các bản ghi khác (nhân sự, lịch hoặc thiết bị). Vui lòng xử lý các dữ liệu liên quan trước khi xóa!"
        if "timeout" in err_str.lower() or "connection" in err_str.lower():
            return "Không thể kết nối đến máy chủ. Vui lòng kiểm tra đường truyền mạng!"

        return fallback

    # ================= AUTHENTICATION =================
    def login(self, email: str, password: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ xác thực. Vui lòng kiểm tra cấu hình mạng!"}

        try:
            response = self.client.auth.sign_in_with_password({
                "email": email.strip(),
                "password": password
            })
            if not response.user:
                return {"success": False, "message": "Đăng nhập thất bại, vui lòng kiểm tra lại tài khoản và mật khẩu!"}

            self.current_user = response.user
            profile_res = self.get_profile(self.current_user.id)
            if not profile_res["success"]:
                return profile_res

            self.current_profile = profile_res["profile"]

            if not self.current_profile.get("is_active", True):
                self.logout()
                return {"success": False, "message": "Tài khoản của bạn đã bị vô hiệu hóa. Vui lòng liên hệ Quản lý!"}

            return {
                "success": True,
                "user": self.current_user,
                "profile": self.current_profile
            }
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Sai tài khoản hoặc mật khẩu đăng nhập!")}

    def logout(self):
        if self.client:
            try:
                self.client.auth.sign_out()
            except Exception:
                pass
        self.current_user = None
        self.current_profile = None

    def get_profile(self, user_id: str) -> dict:
        try:
            res = self.client.table("profiles").select("*, branches(name, address)").eq("id", user_id).single().execute()
            if res.data:
                return {"success": True, "profile": res.data}
            return {"success": False, "message": "Không tìm thấy hồ sơ người dùng!"}
        except Exception as e:
            return {"success": False, "message": f"Lỗi đọc hồ sơ: {str(e)}"}

    # ================= DEVICE VALIDATION =================
    def check_device_permission(self, branch_id: str, device_uuid: str) -> bool:
        if not self.client:
            return False
        try:
            res = self.client.table("allowed_devices") \
                .select("id") \
                .eq("branch_id", branch_id) \
                .eq("device_uuid", device_uuid) \
                .eq("is_active", True) \
                .execute()
            return len(res.data) > 0
        except Exception as e:
            print(f"[LỖI] Kiểm tra thiết bị: {e}")
            return False

    def get_allowed_devices(self, branch_id: str = None) -> list:
        if not self.client:
            return []
        try:
            query = self.client.table("allowed_devices").select("*, branches(name)")
            if branch_id:
                query = query.eq("branch_id", branch_id)
            res = query.order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"[LỖI] Đọc danh sách thiết bị: {e}")
            return []

    def register_device(self, branch_id: str, device_uuid: str, device_name: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("allowed_devices").insert({
                "branch_id": branch_id,
                "device_uuid": device_uuid,
                "device_name": device_name,
                "is_active": True
            }).execute()
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể đăng ký máy tính này vào hệ thống.")}

    def toggle_device_status(self, device_id: str, is_active: bool) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            self.client.table("allowed_devices").update({"is_active": is_active}).eq("id", device_id).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể thay đổi trạng thái thiết bị.")}

    def update_device(self, device_id: str, branch_id: str, device_name: str, is_active: bool = True) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            self.client.table("allowed_devices").update({
                "branch_id": branch_id,
                "device_name": device_name,
                "is_active": is_active
            }).eq("id", device_id).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể cập nhật thông tin thiết bị.")}

    def delete_device(self, device_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            self.client.table("allowed_devices").delete().eq("id", device_id).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể xóa thiết bị.")}

    # ================= BRANCHES =================
    def get_branches(self, force_refresh: bool = False) -> list:
        if not self.client:
            return []
        if not force_refresh and self._cache.get("branches") is not None:
            return self._cache["branches"]
        try:
            res = self.client.table("branches").select("*").order("name").execute()
            data = res.data or []
            self._cache["branches"] = data
            return data
        except Exception as e:
            print(f"[SECURITY/LOG] Lỗi đọc branches: {e}")
            return []

    def create_branch(self, name: str, address: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("branches").insert({"name": name, "address": address}).execute()
            self._cache["branches"] = None  # Xóa cache
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể tạo chi nhánh mới.")}

    def update_branch(self, branch_id: str, name: str, address: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            self.client.table("branches").update({"name": name, "address": address}).eq("id", branch_id).execute()
            self._cache["branches"] = None
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể cập nhật chi nhánh.")}

    def delete_branch(self, branch_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            self.client.table("branches").delete().eq("id", branch_id).execute()
            self._cache["branches"] = None
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Chi nhánh này đang có nhân sự, ca làm hoặc máy tính liên kết. Vui lòng chuyển các mục đó trước khi xóa!")}

    # ================= USERS / PROFILES =================
    def get_staff_list(self, branch_id: str = None, force_refresh: bool = False) -> list:
        if not self.client:
            return []
        if not force_refresh and not branch_id and self._cache.get("staffs") is not None:
            return self._cache["staffs"]
        try:
            query = self.client.table("profiles").select("*, branches(name)")
            if branch_id:
                query = query.eq("branch_id", branch_id)
            res = query.order("full_name").execute()
            data = res.data or []
            if not branch_id:
                self._cache["staffs"] = data
            return data
        except Exception as e:
            print(f"[SECURITY/LOG] Lỗi đọc danh sách nhân viên: {e}")
            return []

    def create_user(self, email: str, password: str, full_name: str, role: str, branch_id: str, phone: str) -> dict:
        """Tạo nhân viên mới thông qua RPC bảo mật, kiểm tra duy nhất 1 Admin và 1 Store Manager/CN"""
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc("rpc_create_user", {
                "p_email": email.strip(),
                "p_password": password,
                "p_full_name": full_name.strip(),
                "p_role": role,
                "p_branch_id": branch_id if branch_id else None,
                "p_phone": phone.strip() if phone else None
            }).execute()
            self._cache["staffs"] = None
            return res.data or {"success": True, "message": f"Tạo tài khoản thành công cho {full_name}!"}
        except Exception as e:
            err_str = str(e)
            print(f"[SECURITY/LOG] Lỗi tạo user: {err_str}")
            if "Chi nhánh này đã có Cửa hàng trưởng" in err_str:
                return {"success": False, "message": "Chi nhánh này đã có Cửa hàng trưởng! Mỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý."}
            if "đã tồn tại" in err_str or "duplicate" in err_str:
                return {"success": False, "message": f"Tên đăng nhập hoặc Email '{email}' đã được sử dụng. Vui lòng chọn tên khác!"}
            return {"success": False, "message": "Không thể tạo tài khoản nhân viên. Vui lòng liên hệ Quản trị viên hệ thống để kiểm tra quyền hạn máy chủ!"}

    def update_user_full(self, user_id: str, full_name: str, role: str, branch_id: str, phone: str, is_active: bool = True) -> dict:
        """Cập nhật thông tin nhân viên qua RPC bảo mật, fallback sang bảng profiles nếu chưa nạp RPC"""
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc("rpc_update_user", {
                "p_user_id": user_id,
                "p_full_name": full_name.strip(),
                "p_role": role,
                "p_branch_id": branch_id if branch_id else None,
                "p_phone": phone.strip() if phone else None,
                "p_is_active": is_active
            }).execute()
            self._cache["staffs"] = None
            return res.data or {"success": True, "message": "Cập nhật thành công!"}
        except Exception as e:
            err_str = str(e)
            if "PGRST202" in err_str or "rpc_update_user" in err_str:
                try:
                    payload = {
                        "full_name": full_name.strip(),
                        "role": role,
                        "branch_id": branch_id if branch_id else None,
                        "phone": phone.strip() if phone else None,
                        "is_active": is_active
                    }
                    self.client.table("profiles").update(payload).eq("id", user_id).execute()
                    self._cache["staffs"] = None
                    return {"success": True, "message": "Cập nhật thành công!"}
                except Exception as inner_e:
                    return {"success": False, "message": self._sanitize_error(inner_e, "Không thể cập nhật hồ sơ nhân sự.")}
            return {"success": False, "message": self._sanitize_error(e, "Không thể cập nhật nhân sự.")}

    def delete_user_full(self, user_id: str) -> dict:
        """Xóa tài khoản nhân viên qua RPC bảo mật, fallback sang xóa profile nếu chưa nạp RPC"""
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc("rpc_delete_user", {"p_user_id": user_id}).execute()
            self._cache["staffs"] = None
            return res.data or {"success": True, "message": "Đã xóa tài khoản nhân viên thành công!"}
        except Exception as e:
            err_str = str(e)
            if "PGRST202" in err_str or "rpc_delete_user" in err_str:
                try:
                    self.client.table("profiles").delete().eq("id", user_id).execute()
                    self._cache["staffs"] = None
                    return {"success": True, "message": "Đã xóa hồ sơ nhân viên thành công!"}
                except Exception as inner_e:
                    return {"success": False, "message": self._sanitize_error(inner_e, "Không thể xóa nhân viên.")}
            return {"success": False, "message": self._sanitize_error(e, "Không thể xóa nhân viên.")}

    def get_branch_storemanager(self, branch_id: str) -> dict:
        """Tìm Cửa hàng trưởng của một chi nhánh nếu có"""
        if not self.client or not branch_id:
            return None
        try:
            res = self.client.table("profiles").select("id, full_name").eq("branch_id", branch_id).eq("role", "storemanager").eq("is_active", True).execute()
            return res.data[0] if res.data else None
        except Exception:
            return None

    def update_profile_role_branch(self, user_id: str, role: str, branch_id: str, is_active: bool = True) -> dict:
        return self.update_user_full(user_id, "", role, branch_id, "", is_active)

    # ================= SHIFTS & SCHEDULES =================
    def get_shifts(self, branch_id: str = None, force_refresh: bool = False) -> list:
        if not self.client:
            return []
        if not force_refresh and not branch_id and self._cache.get("shifts") is not None:
            return self._cache["shifts"]
        try:
            query = self.client.table("shifts").select("*, branches(name)")
            if branch_id:
                query = query.eq("branch_id", branch_id)
            res = query.order("start_time").execute()
            data = res.data or []
            if not branch_id:
                self._cache["shifts"] = data
            return data
        except Exception as e:
            print(f"[LỖI] Đọc ca làm việc: {e}")
            return []

    def create_shift(self, branch_id: str, name: str, start_time: str, end_time: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("shifts").insert({
                "branch_id": branch_id,
                "name": name,
                "start_time": start_time,
                "end_time": end_time
            }).execute()
            self._cache["shifts"] = None  # Xóa cache
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể tạo ca làm việc mới.")}

    def update_shift(self, shift_id: str, branch_id: str, name: str, start_time: str, end_time: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            self.client.table("shifts").update({
                "branch_id": branch_id,
                "name": name,
                "start_time": start_time,
                "end_time": end_time
            }).eq("id", shift_id).execute()
            self._cache["shifts"] = None
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể cập nhật ca làm việc.")}

    def delete_shift(self, shift_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            self.client.table("shifts").delete().eq("id", shift_id).execute()
            self._cache["shifts"] = None
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Ca làm việc này đã được phân công trong lịch làm việc, không thể xóa!")}

    def get_today_schedule(self, user_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        today_str = date.today().isoformat()
        try:
            res = self.client.table("schedules") \
                .select("*, shifts(name, start_time, end_time), attendance(*)") \
                .eq("user_id", user_id) \
                .eq("work_date", today_str) \
                .execute()
            return {"success": True, "schedules": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể đọc dữ liệu lịch ca hôm nay.")}

    def get_schedules_range(self, branch_id: str = None, user_id: str = None, start_date: str = None, end_date: str = None) -> list:
        if not self.client:
            return []
        try:
            query = self.client.table("schedules").select(
                "*, profiles(full_name, role), shifts(name, start_time, end_time), attendance(check_in, check_out, is_late, late_minutes)"
            )
            if branch_id:
                query = query.eq("branch_id", branch_id)
            if user_id:
                query = query.eq("user_id", user_id)
            if start_date:
                query = query.gte("work_date", start_date)
            if end_date:
                query = query.lte("work_date", end_date)

            res = query.order("work_date").execute()
            return res.data or []
        except Exception as e:
            print(f"[SECURITY/LOG] Lỗi đọc lịch: {e}")
            return []

    def create_schedule(self, branch_id: str, user_id: str, shift_id: str, work_date: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("schedules").insert({
                "branch_id": branch_id,
                "user_id": user_id,
                "shift_id": shift_id,
                "work_date": work_date,
                "status": "scheduled"
            }).execute()
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể xếp ca làm việc. Vui lòng kiểm tra lại thông tin!")}

    def delete_schedule(self, schedule_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            self.client.table("schedules").delete().eq("id", schedule_id).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể xóa lịch làm việc này.")}

    # ================= ATTENDANCE RPC =================
    def check_in(self, schedule_id: str, device_uuid: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc("rpc_check_in", {
                "p_schedule_id": schedule_id,
                "p_device_uuid": device_uuid
            }).execute()
            return res.data
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể thực hiện Check-in. Vui lòng thử lại!")}

    def check_out(self, attendance_id: str, device_uuid: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc("rpc_check_out", {
                "p_attendance_id": attendance_id,
                "p_device_uuid": device_uuid
            }).execute()
            return res.data
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể thực hiện Check-out. Vui lòng thử lại!")}

    def get_attendance_history(self, branch_id: str = None, user_id: str = None, date_str: str = None, limit: int = 150) -> list:
        """Đọc danh sách chi tiết các bản ghi Check-in / Check-out phục vụ xem lịch sử và tra cứu"""
        if not self.client:
            return []
        try:
            query = self.client.table("attendance").select(
                "*, profiles(full_name, role, phone), branches(name), schedules(work_date, shifts(name, start_time, end_time))"
            )
            if branch_id:
                query = query.eq("branch_id", branch_id)
            if user_id:
                query = query.eq("user_id", user_id)
            if date_str:
                query = query.gte("check_in", f"{date_str}T00:00:00").lte("check_in", f"{date_str}T23:59:59")

            res = query.order("check_in", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            print(f"[SECURITY/LOG] Lỗi đọc lịch sử chấm công: {e}")
            return []

    # ================= LEAVE REQUESTS =================
    def submit_leave_request(self, schedule_id: str, branch_id: str, leave_type: str, reason: str) -> dict:
        if not self.client or not self.current_user:
            return {"success": False, "message": "Chưa đăng nhập!"}
        try:
            res = self.client.table("leave_requests").insert({
                "user_id": self.current_user.id,
                "branch_id": branch_id,
                "schedule_id": schedule_id,
                "leave_type": leave_type,
                "reason": reason,
                "status": "pending"
            }).execute()
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể gửi đơn xin nghỉ. Vui lòng thử lại!")}

    def get_leave_requests(self, branch_id: str = None, status: str = None) -> list:
        if not self.client:
            return []
        try:
            query = self.client.table("leave_requests").select(
                "*, profiles!leave_requests_user_id_fkey(full_name), schedules(work_date, shifts(name, start_time, end_time)), branches(name)"
            )
            if branch_id:
                query = query.eq("branch_id", branch_id)
            if status:
                query = query.eq("status", status)
            res = query.order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"[SECURITY/LOG] Lỗi đọc đơn xin nghỉ: {e}")
            return []

    def review_leave_request(self, request_id: str, status: str, reviewer_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("leave_requests").update({
                "status": status,
                "reviewed_by": reviewer_id
            }).eq("id", request_id).execute()
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể cập nhật trạng thái đơn.")}

    # ================= ATTENDANCE PROOFS =================
    def upload_compressed_proof(self, image_path: str, user_id: str, branch_id: str = None, note: str = "") -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            with Image.open(image_path) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                max_width = 1280
                if img.width > max_width:
                    ratio = max_width / float(img.width)
                    new_height = int(float(img.height) * float(ratio))
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=75, optimize=True)
                buffer.seek(0)
                file_bytes = buffer.getvalue()

            filename = f"{user_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
            bucket_name = "attendance_proofs"

            self.client.storage.from_(bucket_name).upload(
                path=filename,
                file=file_bytes,
                file_options={"content-type": "image/jpeg"}
            )
            public_url = self.client.storage.from_(bucket_name).get_public_url(filename)

            # Tạo bản ghi attendance_proofs
            self.client.table("attendance_proofs").insert({
                "user_id": user_id,
                "branch_id": branch_id,
                "image_url": public_url,
                "note": note,
                "status": "pending"
            }).execute()

            return {"success": True, "url": public_url}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể tải lên ảnh minh chứng. Vui lòng thử lại!")}

    def get_attendance_proofs(self, branch_id: str = None, status: str = None) -> list:
        if not self.client:
            return []
        try:
            query = self.client.table("attendance_proofs").select(
                "*, profiles!attendance_proofs_user_id_fkey(full_name), branches(name)"
            )
            if branch_id:
                query = query.eq("branch_id", branch_id)
            if status:
                query = query.eq("status", status)
            res = query.order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"[SECURITY/LOG] Lỗi đọc minh chứng: {e}")
            return []

    def review_attendance_proof(self, proof_id: str, status: str, reviewer_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("attendance_proofs").update({
                "status": status,
                "reviewed_by": reviewer_id
            }).eq("id", proof_id).execute()
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể cập nhật minh chứng.")}
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ================= REPORT DATA =================
    def get_monthly_attendance_data(self, branch_id: str, year: int, month: int) -> list:
        if not self.client:
            return []
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year+1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month+1:02d}-01"

        try:
            query = self.client.table("schedules").select(
                "id, work_date, status, profiles(id, full_name, role), shifts(name, start_time, end_time), attendance(check_in, check_out, is_late, late_minutes, is_early_leave, early_minutes)"
            )
            if branch_id:
                query = query.eq("branch_id", branch_id)
            query = query.gte("work_date", start_date).lt("work_date", end_date)
            res = query.execute()
            return res.data or []
        except Exception as e:
            print(f"[LỖI] Đọc dữ liệu báo cáo: {e}")
            return []
