import subprocess
import uuid
import sys
import logging
from functools import lru_cache
from threading import Lock

_identity_lock = Lock()

# Đảm bảo mã hóa UTF-8 cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def get_hardware_uuid() -> str:
    """Resolve once per process; callers must perform cold lookup in a worker."""
    with _identity_lock:
        return _resolve_hardware_uuid()


@lru_cache(maxsize=1)
def _resolve_hardware_uuid() -> str:
    """
    Lấy mã định danh phần cứng duy nhất (Hardware UUID / Serial) của máy tính.
    Sử dụng PowerShell Get-CimInstance (chống lỗi deprecated wmic trên Windows 11).
    """
    if sys.platform != "win32":
        # Fallback cho môi trường test trên macOS / Linux
        return str(uuid.UUID(int=uuid.getnode()))

    try:
        # Cách 1: Lấy BIOS/Motherboard UUID qua PowerShell CIM (Khuyến nghị chuẩn của Microsoft)
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        output = result.stdout.strip()
        if output and "FFFFFFFF" not in output and len(output) >= 16:
            return output

        # Cách 2: Lấy ProcessorId nếu UUID bị lỗi
        cmd_cpu = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "(Get-CimInstance -ClassName Win32_Processor).ProcessorId",
        ]
        result_cpu = subprocess.run(
            cmd_cpu,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        output_cpu = result_cpu.stdout.strip()
        if output_cpu:
            return output_cpu

    except Exception as e:
        logging.getLogger(__name__).warning("Device identity lookup failed: %s", type(e).__name__)

    # Fallback cuối cùng: Lấy MAC-based UUID qua python uuid module
    return str(uuid.UUID(int=uuid.getnode()))


if __name__ == "__main__":
    device_id = get_hardware_uuid()
    print("=== HARDWARE DEVICE UUID ===")
    print(f"Device UUID: {device_id}")
