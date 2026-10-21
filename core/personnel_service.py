"""Admin-only personnel/payroll RPC boundary; never falls back to direct writes."""

from core.security import requires_roles
from core.ui_messages import SYSTEM_UNAVAILABLE, public_mutation_result


class PersonnelServiceMixin:
    def _personnel_rpc(self, name: str, params: dict) -> dict:
        if not self.client:
            return {"success": False, "message": SYSTEM_UNAVAILABLE}
        try:
            data = self.client.rpc(name, params).execute().data
            if name in ("rpc_payroll_page", "rpc_upcoming_birthdays"):
                if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
                    raise ValueError("Invalid list response")
            if name == "rpc_employee_private" and (
                not isinstance(data, dict) or not isinstance(data.get("terms"), list)
                or (data.get("details") is not None and not isinstance(data["details"], dict))
            ):
                raise ValueError("Invalid private response")
            if name == "rpc_payroll_preview" and (
                not isinstance(data, dict) or not isinstance(data.get("warnings"), list)
                or not isinstance(data.get("days"), list)
            ):
                raise ValueError("Invalid payroll response")
            if isinstance(data, dict) and "success" in data:
                return public_mutation_result(data)
            if not isinstance(data, (dict, list)):
                raise ValueError("Invalid RPC response")
            return {"success": True, "data": data}
        except Exception as exc:
            # Only fixed error tokens map to UI text; raw errors can contain PII.
            messages = {
                "PERSONNEL_FORBIDDEN": "Chỉ admin được xem hoặc thay đổi nhân sự và lương.",
                "PERSONNEL_STALE": "Dữ liệu đã thay đổi. Đóng cửa sổ, tải lại rồi thực hiện lại.",
                "PAYROLL_LOCKED": "Kỳ lương đã chốt; không thể sửa chế độ hoặc phân loại ngày của kỳ này.",
                "PAYROLL_NOT_READY": "Chưa hết tháng hoặc còn cảnh báo cần xử lý trước khi chốt.",
                "PERSONNEL_INVALID": "Thông tin không hợp lệ. Kiểm tra ngày, số tiền và các trường bắt buộc.",
            }
            raw = str(exc)
            if str(getattr(exc, "code", "")) == "23505":
                return {"success": False, "message": "Thông tin bị trùng. Kiểm tra mã nhân viên hoặc kỳ lương."}
            message = next((text for token, text in messages.items() if token in raw),
                           SYSTEM_UNAVAILABLE)
            return {"success": False, "message": message}

    @requires_roles("admin")
    def get_employee_private(self, user_id: str) -> dict:
        return self._personnel_rpc("rpc_employee_private", {"p_user_id": user_id})

    @requires_roles("admin")
    def save_employee_private(self, user_id: str, details: dict, revision: int) -> dict:
        return self._personnel_rpc("rpc_save_employee_private", {
            "p_user_id": user_id, "p_details": details, "p_revision": revision})

    @requires_roles("admin")
    def save_pay_terms(self, user_id: str, month: str, terms: dict, revision: int) -> dict:
        return self._personnel_rpc("rpc_save_pay_terms", {
            "p_user_id": user_id, "p_month": month, "p_terms": terms, "p_revision": revision})

    @requires_roles("admin")
    def set_payroll_day(self, user_id: str, work_date: str, kind: str, note: str, revision: int) -> dict:
        return self._personnel_rpc("rpc_set_payroll_day", {
            "p_user_id": user_id, "p_date": work_date, "p_kind": kind, "p_note": note, "p_revision": revision})

    @requires_roles("admin")
    def get_payroll_page(self, month: str, offset: int = 0, limit: int = 21,
                         search: str = "", branch_id: str | None = None) -> dict:
        return self._personnel_rpc("rpc_payroll_page", {
            "p_month": month, "p_offset": offset, "p_limit": limit, "p_search": search, "p_branch_id": branch_id})

    @requires_roles("admin")
    def get_payroll_preview(self, user_id: str, month: str) -> dict:
        return self._personnel_rpc("rpc_payroll_preview", {"p_user_id": user_id, "p_month": month})

    @requires_roles("admin")
    def finalize_payroll(self, user_id: str, month: str, signature: str) -> dict:
        return self._personnel_rpc("rpc_finalize_payroll", {
            "p_user_id": user_id, "p_month": month, "p_signature": signature})

    @requires_roles("admin")
    def get_upcoming_birthdays(self, offset: int = 0, limit: int = 51) -> dict:
        return self._personnel_rpc("rpc_upcoming_birthdays", {"p_offset": offset, "p_limit": limit})
