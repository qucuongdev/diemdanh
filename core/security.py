"""Client configuration checks. Database policies remain the authority."""

import base64
import json
from core.ui_messages import UserInputError


def validate_public_key(key: str) -> None:
    if key.startswith("sb_publishable_"):
        return
    if key.count(".") == 2:
        try:
            payload = key.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except (ValueError, TypeError):
            raise ValueError("Invalid Supabase key") from None
        if isinstance(claims, dict) and claims.get("role") == "anon":
            return
    raise ValueError("Only public Supabase keys are allowed in desktop clients")


def requires_roles(*roles):
    from functools import wraps
    from core.domain import validate_profile

    def decorate(method):
        @wraps(method)
        def guarded(self, *args, **kwargs):
            try:
                profile = validate_profile(self.current_profile)
                if profile["role"] not in roles:
                    raise UserInputError("Bạn không có quyền thực hiện thao tác này.")
            except UserInputError as exc:
                return {"success": False, "message": str(exc)}
            return method(self, *args, **kwargs)

        return guarded

    return decorate
