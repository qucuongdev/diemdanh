import io
import uuid
from datetime import datetime, date, timedelta
from urllib.parse import urlparse, unquote
import logging
from core.domain import LOCAL_TZ, local_now, validate_profile, first_attendance
from core.security import validate_public_key, requires_roles
from core.personnel_service import PersonnelServiceMixin
from core.ui_messages import SYSTEM_UNAVAILABLE, CONNECTION_UNAVAILABLE, public_mutation_result
from PIL import Image
from supabase import create_client, Client, ClientOptions
from httpx import TransportError
from core.config import SUPABASE_URL, SUPABASE_KEY, BACKEND_VERSION


class ServiceError(RuntimeError):
    pass


class SupabaseService(PersonnelServiceMixin):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseService, cls).__new__(cls)
            cls._instance.client: Client = None
            cls._instance.current_user = None
            cls._instance.current_profile = None
            cls._instance._cache = {"branches": None, "staffs": None, "shifts": None}
            cls._instance.init_client()
        return cls._instance

    def init_client(self):
        self.configuration_error = SYSTEM_UNAVAILABLE
        if SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL != "https://your-project-id.supabase.co":
            try:
                validate_public_key(SUPABASE_KEY)
                self.client = create_client(
                    SUPABASE_URL,
                    SUPABASE_KEY,
                    options=ClientOptions(postgrest_client_timeout=15, storage_client_timeout=20),
                )
                self.configuration_error = ""
            except Exception as e:
                logging.getLogger(__name__).warning("Supabase configuration rejected: %s", type(e).__name__)
                self.configuration_error = SYSTEM_UNAVAILABLE
                self.client = None
        else:
            self.client = None

    def is_configured(self) -> bool:
        return self.client is not None

    def check_backend(self):
        """Retain internal diagnostic codes; show only generic public messages."""
        try:
            version = self.client.rpc("rpc_client_version", {}).execute().data
        except Exception as exc:
            code = str(getattr(exc, "code", ""))
            logging.getLogger(__name__).warning("Backend compatibility check failed: %s", type(exc).__name__)
            if code in ("PGRST202", "42883"):
                return {"success": False, "code": "backend_missing", "message":
                    SYSTEM_UNAVAILABLE}
            if code in ("42501", "PGRST301", "PGRST302", "PGRST303"):
                return {"success": False, "code": "backend_permission", "message":
                    SYSTEM_UNAVAILABLE}
            if isinstance(exc, (TransportError, ConnectionError, TimeoutError)):
                return {"success": False, "code": "backend_network", "message":
                    CONNECTION_UNAVAILABLE}
            return {"success": False, "code": "backend_check_failed", "message":
                SYSTEM_UNAVAILABLE}
        if type(version) is not int or version != BACKEND_VERSION:
            return {"success": False, "code": "backend_incompatible", "message":
                SYSTEM_UNAVAILABLE}
        return {"success": True}

    def _sanitize_error(
        self,
        err: Exception,
        fallback: str = "Thao tác không thành công. Vui lòng kiểm tra kết nối mạng và thử lại!",
    ) -> str:
        """Bảo mật: Ghi log nội bộ cho Sysadmin/Dev, tuyệt đối KHÔNG để lộ chi tiết database, mã lỗi hay kiến trúc máy chủ ra ngoài giao diện"""
        err_str = str(err)
        logging.getLogger(__name__).warning("Service operation failed: %s", type(err).__name__)

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
        if "Chưa đến giờ tan ca" in err_str:
            return "Chưa đến giờ tan ca theo giờ máy chủ. Vui lòng chờ hết ca."
        if "Ca này đã được Check-out" in err_str:
            return "Ca này đã được ghi nhận tan ca. Hãy làm mới dữ liệu."
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
            return {
                "success": False,
                "message": self.configuration_error,
            }

        try:
            response = self.client.auth.sign_in_with_password({"email": email.strip(), "password": password})
            if not response.user:
                return {
                    "success": False,
                    "message": "Đăng nhập thất bại, vui lòng kiểm tra lại tài khoản và mật khẩu!",
                }

            self.current_user = response.user
            profile_res = self.get_profile(self.current_user.id)
            if not profile_res["success"]:
                self.logout()
                return profile_res

            self.current_profile = profile_res["profile"]

            if not self.current_profile.get("is_active", False):
                self.logout()
                return {
                    "success": False,
                    "message": "Tài khoản của bạn đã bị vô hiệu hóa. Vui lòng liên hệ Quản lý!",
                }

            validate_profile(self.current_profile)
            compatibility = self.check_backend()
            if not compatibility["success"]:
                self.logout()
                return compatibility
            return {"success": True, "user": self.current_user, "profile": self.current_profile}
        except Exception as e:
            self.logout()
            return {
                "success": False,
                "message": self._sanitize_error(e, "Sai tài khoản hoặc mật khẩu đăng nhập!"),
            }

    def logout(self):
        if self.client:
            try:
                self.client.auth.sign_out()
            except Exception:
                pass
        self.current_user = None
        self.current_profile = None
        self._cache = {"branches": None, "staffs": None, "shifts": None}

    def get_profile(self, user_id: str) -> dict:
        try:
            res = (
                self.client.table("profiles")
                .select("*, branches(name, address)")
                .eq("id", user_id)
                .single()
                .execute()
            )
            if res.data:
                return {"success": True, "profile": res.data}
            return {"success": False, "message": "Không tìm thấy hồ sơ người dùng!"}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể đọc hồ sơ tài khoản.")}

    # ================= DEVICE VALIDATION =================
    def check_device_permission(self, branch_id: str, device_uuid: str) -> bool:
        if not self.client:
            return False
        try:
            res = (
                self.client.table("allowed_devices")
                .select("id")
                .eq("branch_id", branch_id)
                .eq("device_uuid", device_uuid)
                .eq("is_active", True)
                .execute()
            )
            return len(res.data) > 0
        except Exception as e:
            logging.getLogger(__name__).warning("Service operation failed: %s", type(e).__name__)
            return False

    def get_allowed_devices(self, branch_id: str = None) -> list:
        if not self.client:
            raise ServiceError("Chưa cấu hình kết nối máy chủ.")
        try:
            query = self.client.table("allowed_devices").select("*, branches(name)")
            if branch_id:
                query = query.eq("branch_id", branch_id)
            return self._all_rows(query.order("created_at", desc=True).order("id"))
        except Exception as e:
            raise ServiceError("Không thể tải dữ liệu. Kiểm tra kết nối và thử lại.") from e

    @requires_roles("admin")
    def register_device(self, branch_id: str, device_uuid: str, device_name: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = (
                self.client.table("allowed_devices")
                .insert(
                    {
                        "branch_id": branch_id,
                        "device_uuid": device_uuid,
                        "device_name": device_name,
                        "is_active": True,
                    }
                )
                .execute()
            )
            return {"success": True, "data": res.data}
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(e, "Không thể đăng ký máy tính này vào hệ thống."),
            }

    @requires_roles("admin")
    def toggle_device_status(self, device_id: str, is_active: bool) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("allowed_devices").update({"is_active": is_active}).eq(
                "id", device_id
            ).execute()
            if not res.data:
                raise ServiceError("Không tìm thấy dữ liệu hoặc bạn không có quyền cập nhật.")
            return {"success": True}
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(e, "Không thể thay đổi trạng thái thiết bị."),
            }

    @requires_roles("admin")
    def update_device(self, device_id: str, branch_id: str, device_name: str, is_active: bool = True) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("allowed_devices").update(
                {"branch_id": branch_id, "device_name": device_name, "is_active": is_active}
            ).eq("id", device_id).execute()
            if not res.data:
                raise ServiceError("Không tìm thấy dữ liệu hoặc bạn không có quyền cập nhật.")
            return {"success": True}
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(e, "Không thể cập nhật thông tin thiết bị."),
            }

    @requires_roles("admin")
    def delete_device(self, device_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("allowed_devices").delete().eq("id", device_id).execute()
            if not res.data:
                raise ServiceError("Không tìm thấy dữ liệu hoặc bạn không có quyền cập nhật.")
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể xóa thiết bị.")}

    # ================= BRANCHES =================
    def get_branches(self, force_refresh: bool = False) -> list:
        if not self.client:
            raise ServiceError("Chưa cấu hình kết nối máy chủ.")
        if not force_refresh and self._cache.get("branches") is not None:
            return self._cache["branches"]
        try:
            data = self._all_rows(self.client.table("branches").select("*").order("name").order("id"))
            self._cache["branches"] = data
            return data
        except Exception as e:
            raise ServiceError("Không thể tải dữ liệu. Kiểm tra kết nối và thử lại.") from e

    @requires_roles("admin")
    def create_branch(self, name: str, address: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("branches").insert({"name": name, "address": address}).execute()
            self._cache["branches"] = None  # Xóa cache
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể tạo chi nhánh mới.")}

    @requires_roles("admin")
    def update_branch(self, branch_id: str, name: str, address: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("branches").update({"name": name, "address": address}).eq(
                "id", branch_id
            ).execute()
            if not res.data:
                raise ServiceError("Không tìm thấy dữ liệu hoặc bạn không có quyền cập nhật.")
            self._cache["branches"] = None
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể cập nhật chi nhánh.")}

    @requires_roles("admin")
    def delete_branch(self, branch_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("branches").delete().eq("id", branch_id).execute()
            if not res.data:
                raise ServiceError("Không tìm thấy dữ liệu hoặc bạn không có quyền cập nhật.")
            self._cache["branches"] = None
            return {"success": True}
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(
                    e,
                    "Chi nhánh này đang có nhân sự, ca làm hoặc máy tính liên kết. Vui lòng chuyển các mục đó trước khi xóa!",
                ),
            }

    # ================= USERS / PROFILES =================
    def get_staff_list(self, branch_id: str = None, force_refresh: bool = False) -> list:
        if not self.client:
            raise ServiceError("Chưa cấu hình kết nối máy chủ.")
        if not force_refresh and not branch_id and self._cache.get("staffs") is not None:
            return self._cache["staffs"]
        try:
            query = self.client.table("profiles").select("*, branches(name)")
            if branch_id:
                query = query.eq("branch_id", branch_id)
            data = self._all_rows(query.order("full_name").order("id"))
            if not branch_id:
                self._cache["staffs"] = data
            return data
        except Exception as e:
            raise ServiceError("Không thể tải dữ liệu. Kiểm tra kết nối và thử lại.") from e

    @requires_roles("admin")
    def create_user(
        self, email: str, password: str, full_name: str, role: str, branch_id: str, phone: str
    ) -> dict:
        """Tạo nhân viên mới thông qua RPC bảo mật, kiểm tra duy nhất 1 Admin và 1 Store Manager/CN"""
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc(
                "rpc_create_user",
                {
                    "p_email": email.strip(),
                    "p_password": password,
                    "p_full_name": full_name.strip(),
                    "p_role": role,
                    "p_branch_id": branch_id if branch_id else None,
                    "p_phone": phone.strip() if phone else None,
                },
            ).execute()
            self._cache["staffs"] = None
            return public_mutation_result(res.data)
        except Exception as e:
            err_str = str(e)
            logging.getLogger(__name__).warning("User creation failed: %s", type(e).__name__)
            if "Chi nhánh này đã có Cửa hàng trưởng" in err_str:
                return {
                    "success": False,
                    "message": "Chi nhánh này đã có Cửa hàng trưởng! Mỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý.",
                }
            if "đã tồn tại" in err_str or "duplicate" in err_str:
                return {
                    "success": False,
                    "message": "Tên đăng nhập hoặc email đã được sử dụng. Vui lòng chọn tên khác.",
                }
            return {
                "success": False,
                "message": SYSTEM_UNAVAILABLE,
            }

    @requires_roles("admin")
    def update_user_full(
        self, user_id: str, full_name: str, role: str, branch_id: str, phone: str, is_active: bool = True
    ) -> dict:
        """Update through the authorized RPC only; fail closed if unavailable."""
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc(
                "rpc_update_user",
                {
                    "p_user_id": user_id,
                    "p_full_name": full_name.strip(),
                    "p_role": role,
                    "p_branch_id": branch_id if branch_id else None,
                    "p_phone": phone.strip() if phone else None,
                    "p_is_active": is_active,
                },
            ).execute()
            self._cache["staffs"] = None
            return public_mutation_result(res.data)
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(
                    e, SYSTEM_UNAVAILABLE
                ),
            }

    @requires_roles("admin")
    def delete_user_full(self, user_id: str) -> dict:
        """Delete through the authorized RPC only; fail closed if unavailable."""
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc("rpc_delete_user", {"p_user_id": user_id}).execute()
            self._cache["staffs"] = None
            return public_mutation_result(res.data)
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(
                    e, SYSTEM_UNAVAILABLE
                ),
            }

    def get_branch_storemanager(self, branch_id: str) -> dict:
        """Tìm Cửa hàng trưởng của một chi nhánh nếu có"""
        if not self.client or not branch_id:
            return None
        try:
            res = (
                self.client.table("profiles")
                .select("id, full_name")
                .eq("branch_id", branch_id)
                .eq("role", "storemanager")
                .eq("is_active", True)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception:
            return None

    def update_profile_role_branch(
        self, user_id: str, role: str, branch_id: str, is_active: bool = True
    ) -> dict:
        return self.update_user_full(user_id, "", role, branch_id, "", is_active)

    # ================= SHIFTS & SCHEDULES =================
    def get_shifts(self, branch_id: str = None, force_refresh: bool = False) -> list:
        if not self.client:
            raise ServiceError("Chưa cấu hình kết nối máy chủ.")
        if not force_refresh and not branch_id and self._cache.get("shifts") is not None:
            return self._cache["shifts"]
        try:
            query = self.client.table("shifts").select("*, branches(name)")
            if branch_id:
                query = query.eq("branch_id", branch_id)
            data = self._all_rows(query.order("start_time").order("id"))
            if not branch_id:
                self._cache["shifts"] = data
            return data
        except Exception as e:
            raise ServiceError("Không thể tải dữ liệu. Kiểm tra kết nối và thử lại.") from e

    @requires_roles("admin", "storemanager")
    def create_shift(self, branch_id: str, name: str, start_time: str, end_time: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = (
                self.client.table("shifts")
                .insert(
                    {"branch_id": branch_id, "name": name, "start_time": start_time, "end_time": end_time}
                )
                .execute()
            )
            self._cache["shifts"] = None  # Xóa cache
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể tạo ca làm việc mới.")}

    @requires_roles("admin", "storemanager")
    def update_shift(self, shift_id: str, branch_id: str, name: str, start_time: str, end_time: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("shifts").update(
                {"branch_id": branch_id, "name": name, "start_time": start_time, "end_time": end_time}
            ).eq("id", shift_id).execute()
            if not res.data:
                raise ServiceError("Không tìm thấy dữ liệu hoặc bạn không có quyền cập nhật.")
            self._cache["shifts"] = None
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể cập nhật ca làm việc.")}

    @requires_roles("admin", "storemanager")
    def delete_shift(self, shift_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("shifts").delete().eq("id", shift_id).execute()
            if not res.data:
                raise ServiceError("Không tìm thấy dữ liệu hoặc bạn không có quyền cập nhật.")
            self._cache["shifts"] = None
            return {"success": True}
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(
                    e, "Ca làm việc này đã được phân công trong lịch làm việc, không thể xóa!"
                ),
            }

    def get_today_schedule(self, user_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        today = local_now().date()
        today_str = today.isoformat()
        try:
            query = (
                self.client.table("schedules")
                .select("*, shifts(name, start_time, end_time), attendance(*)")
                .eq("user_id", user_id)
                .gte("work_date", (today - timedelta(days=1)).isoformat())
                .lte("work_date", today_str)
            )
            schedules = []
            for record in self._all_rows(query.order("work_date").order("id")):
                shift = record.get("shifts") or {}
                attendance = first_attendance(record)
                overnight = shift.get("end_time", "") <= shift.get("start_time", "")
                if record.get("work_date") == today_str or (
                    overnight and attendance and not attendance.get("check_out")
                ):
                    schedules.append(record)
            return {"success": True, "schedules": schedules}
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(e, "Không thể đọc dữ liệu lịch ca hôm nay."),
            }

    def get_schedules_range(
        self, branch_id: str = None, user_id: str = None, start_date: str = None, end_date: str = None
    ) -> list:
        if not self.client:
            raise ServiceError("Chưa cấu hình kết nối máy chủ.")
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

            return self._all_rows(query.order("work_date").order("id"))
        except Exception as e:
            raise ServiceError("Không thể tải dữ liệu. Kiểm tra kết nối và thử lại.") from e

    @requires_roles("admin", "storemanager")
    def create_schedule(self, branch_id: str, user_id: str, shift_id: str, work_date: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = (
                self.client.table("schedules")
                .insert(
                    {
                        "branch_id": branch_id,
                        "user_id": user_id,
                        "shift_id": shift_id,
                        "work_date": work_date,
                        "status": "scheduled",
                    }
                )
                .execute()
            )
            return {"success": True, "data": res.data}
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(
                    e, "Không thể xếp ca làm việc. Vui lòng kiểm tra lại thông tin!"
                ),
            }

    @requires_roles("admin", "storemanager")
    def delete_schedule(self, schedule_id: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.table("schedules").delete().eq("id", schedule_id).execute()
            if not res.data:
                raise ServiceError("Không tìm thấy dữ liệu hoặc bạn không có quyền cập nhật.")
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể xóa lịch làm việc này.")}

    # ================= ATTENDANCE RPC =================
    def check_in(self, schedule_id: str, device_uuid: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc(
                "rpc_check_in", {"p_schedule_id": schedule_id, "p_device_uuid": device_uuid}
            ).execute()
            return public_mutation_result(res.data)
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(e, "Không thể thực hiện Check-in. Vui lòng thử lại!"),
            }

    def check_out(self, attendance_id: str, device_uuid: str) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = self.client.rpc(
                "rpc_check_out", {"p_attendance_id": attendance_id, "p_device_uuid": device_uuid}
            ).execute()
            return public_mutation_result(res.data)
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(e, "Không thể thực hiện Check-out. Vui lòng thử lại!"),
            }

    def get_attendance_history(
        self,
        branch_id: str = None,
        user_id: str = None,
        date_str: str = None,
        limit: int = 51,
        offset: int = 0,
    ) -> list:
        """Đọc danh sách chi tiết các bản ghi Check-in / Check-out phục vụ xem lịch sử và tra cứu"""
        if not self.client:
            raise ServiceError("Chưa cấu hình kết nối máy chủ.")
        try:
            query = self.client.table("attendance").select(
                "*, profiles(full_name, role, phone), branches(name), schedules(work_date, shifts(name, start_time, end_time))"
            )
            if branch_id:
                query = query.eq("branch_id", branch_id)
            if user_id:
                query = query.eq("user_id", user_id)
            if date_str:
                start = datetime.combine(date.fromisoformat(date_str), datetime.min.time(), tzinfo=LOCAL_TZ)
                query = query.gte("check_in", start.isoformat()).lt(
                    "check_in", (start + timedelta(days=1)).isoformat()
                )

            res = (
                query.order("check_in", desc=True)
                .order("id")
                .range(offset, offset + min(limit, 201) - 1)
                .execute()
            )
            return res.data or []
        except Exception as e:
            raise ServiceError("Không thể tải dữ liệu. Kiểm tra kết nối và thử lại.") from e

    # ================= LEAVE REQUESTS =================
    def submit_leave_request(self, schedule_id: str, branch_id: str, leave_type: str, reason: str) -> dict:
        if not self.client or not self.current_user:
            return {"success": False, "message": "Chưa đăng nhập!"}
        try:
            res = (
                self.client.table("leave_requests")
                .insert(
                    {
                        "user_id": self.current_user.id,
                        "branch_id": branch_id,
                        "schedule_id": schedule_id,
                        "leave_type": leave_type,
                        "reason": reason,
                        "status": "pending",
                    }
                )
                .execute()
            )
            return {"success": True, "data": res.data}
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(e, "Không thể gửi đơn xin nghỉ. Vui lòng thử lại!"),
            }

    def get_leave_requests(
        self, branch_id: str = None, status: str = None, limit: int = 51, offset: int = 0
    ) -> list:
        if not self.client:
            raise ServiceError("Chưa cấu hình kết nối máy chủ.")
        try:
            query = self.client.table("leave_requests").select(
                "*, profiles!leave_requests_user_id_fkey(full_name), schedules(work_date, shifts(name, start_time, end_time)), branches(name)"
            )
            if branch_id:
                query = query.eq("branch_id", branch_id)
            if status:
                query = query.eq("status", status)
            res = (
                query.order("created_at", desc=True)
                .order("id")
                .range(offset, offset + min(limit, 201) - 1)
                .execute()
            )
            return res.data or []
        except Exception as e:
            raise ServiceError("Không thể tải dữ liệu. Kiểm tra kết nối và thử lại.") from e

    @requires_roles("admin", "storemanager")
    def review_leave_request(self, request_id: str, status: str, reviewer_id: str) -> dict:
        if status not in ("approved", "rejected") or reviewer_id != self.current_profile.get("id"):
            return {"success": False, "message": "Thông tin phê duyệt không hợp lệ."}
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = (
                self.client.table("leave_requests")
                .update({"status": status, "reviewed_by": reviewer_id})
                .eq("id", request_id)
                .eq("status", "pending")
                .execute()
            )
            if not res.data:
                return {"success": False, "message": "Yêu cầu đã được xử lý hoặc bạn không có quyền duyệt."}
            return {"success": True, "data": res.data}
        except Exception as e:
            return {
                "success": False,
                "message": self._sanitize_error(e, "Không thể cập nhật trạng thái đơn."),
            }

    # ================= ATTENDANCE PROOFS =================
    def upload_compressed_proof(
        self, image_path: str, user_id: str, branch_id: str = None, note: str = ""
    ) -> dict:
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        filename = None
        uploaded = False
        try:
            if (
                not self.current_profile
                or not branch_id
                or not note.strip()
                or user_id != self.current_profile.get("id")
            ):
                return {"success": False, "message": "Cần chi nhánh và nội dung giải trình hợp lệ."}
            from PIL import ImageOps

            with Image.open(image_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=75, optimize=True)
                buffer.seek(0)
                file_bytes = buffer.getvalue()

            if len(file_bytes) > 500 * 1024:
                return {"success": False, "message": "Ảnh sau nén vượt quá 500 KB. Chọn ảnh nhỏ hơn."}

            filename = f"{user_id}/{local_now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
            bucket_name = "attendance_proofs"

            self.client.storage.from_(bucket_name).upload(
                path=filename, file=file_bytes, file_options={"content-type": "image/jpeg"}
            )
            uploaded = True
            public_url = filename  # Store a private object path; sign only when viewing.

            # Tạo bản ghi attendance_proofs
            self.client.table("attendance_proofs").insert(
                {
                    "user_id": user_id,
                    "branch_id": branch_id,
                    "image_url": public_url,
                    "note": note,
                    "status": "pending",
                }
            ).execute()

            return {"success": True, "url": public_url}
        except Exception as e:
            if uploaded and filename:
                try:
                    self.client.storage.from_("attendance_proofs").remove([filename])
                except Exception:
                    pass
            return {
                "success": False,
                "message": self._sanitize_error(e, "Không thể tải lên ảnh minh chứng. Vui lòng thử lại!"),
            }

    def get_attendance_proofs(
        self, branch_id: str = None, status: str = None, limit: int = 51, offset: int = 0
    ) -> list:
        if not self.client:
            raise ServiceError("Chưa cấu hình kết nối máy chủ.")
        try:
            query = self.client.table("attendance_proofs").select(
                "*, profiles!attendance_proofs_user_id_fkey(full_name), branches(name)"
            )
            if branch_id:
                query = query.eq("branch_id", branch_id)
            if status:
                query = query.eq("status", status)
            res = (
                query.order("created_at", desc=True)
                .order("id")
                .range(offset, offset + min(limit, 201) - 1)
                .execute()
            )
            return res.data or []
        except Exception as e:
            raise ServiceError("Không thể tải dữ liệu. Kiểm tra kết nối và thử lại.") from e

    @requires_roles("admin", "storemanager")
    def review_attendance_proof(self, proof_id: str, status: str, reviewer_id: str) -> dict:
        if status not in ("approved", "rejected") or reviewer_id != self.current_profile.get("id"):
            return {"success": False, "message": "Thông tin phê duyệt không hợp lệ."}
        if not self.client:
            return {"success": False, "message": "Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng!"}
        try:
            res = (
                self.client.table("attendance_proofs")
                .update({"status": status, "reviewed_by": reviewer_id})
                .eq("id", proof_id)
                .eq("status", "pending")
                .execute()
            )
            if not res.data:
                return {"success": False, "message": "Yêu cầu đã được xử lý hoặc bạn không có quyền duyệt."}
            return {"success": True, "data": res.data}
        except Exception as e:
            return {"success": False, "message": self._sanitize_error(e, "Không thể cập nhật minh chứng.")}

    # ================= REPORT DATA =================
    def get_monthly_attendance_data(self, branch_id: str, year: int, month: int) -> list:
        if not self.client:
            raise ServiceError("Chưa cấu hình kết nối máy chủ.")
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month + 1:02d}-01"

        try:
            query = self.client.table("schedules").select(
                "id, work_date, status, profiles(id, full_name, role), shifts(name, start_time, end_time), attendance(check_in, check_out, is_late, late_minutes, is_early_leave, early_minutes)"
            )
            if branch_id:
                query = query.eq("branch_id", branch_id)
            query = query.gte("work_date", start_date).lt("work_date", end_date)
            return self._all_rows(query.order("work_date").order("id"))
        except Exception as e:
            raise ServiceError("Không thể tải dữ liệu. Kiểm tra kết nối và thử lại.") from e

    def _all_rows(self, query):
        rows = []
        offset = 0
        while True:
            batch = query.range(offset, offset + 499).execute().data or []
            rows.extend(batch)
            if not batch:
                return rows
            offset += len(batch)

    def get_proof_url(self, stored_path):
        path = str(stored_path or "")
        if path.startswith("http"):
            parsed = urlparse(path)
            if parsed.netloc != urlparse(SUPABASE_URL).netloc:
                raise ServiceError("Đường dẫn minh chứng không hợp lệ.")
            marker = "/attendance_proofs/"
            if marker not in parsed.path:
                raise ServiceError("Đường dẫn minh chứng không hợp lệ.")
            path = unquote(parsed.path.split(marker, 1)[1])
        if not path or ".." in path.split("/"):
            raise ServiceError("Đường dẫn minh chứng không hợp lệ.")
        result = self.client.storage.from_("attendance_proofs").create_signed_url(path, 120)
        return result.get("signedURL") or result.get("signedUrl")
