import sys
import time
import os
import ctypes
from ctypes import wintypes
import customtkinter as ctk

# Đảm bảo UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
    ]

def get_memory_mb():
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        kernel32 = ctypes.WinDLL('kernel32')
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.WinDLL('psapi')
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = kernel32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / 1024 / 1024
    except Exception:
        pass
    return 0.0

def run_performance_benchmark():
    print("=" * 70)
    print("CÔNG CỤ ĐO HIỆU NĂNG GIAO DIỆN CHUẨN KỸ SƯ (GUI PERFORMANCE BENCHMARK)")
    print("=" * 70)

    init_mem_mb = get_memory_mb()
    print(f"[THÔNG TIN HỆ THỐNG]:")
    print(f"  - Python: {sys.version.split()[0]}")
    print(f"  - CustomTkinter: {ctk.__version__}")
    print(f"  - RAM Ban đầu: {init_mem_mb:.2f} MB")
    print(f"  - CPU Cores: {os.cpu_count()}")

    # 1. Khởi tạo App
    t0 = time.perf_counter()
    from main import App
    app = App()
    app.update_idletasks()
    init_app_time = (time.perf_counter() - t0) * 1000
    print(f"\n[1. KHỞI TẠO APPLICATION ROOT]:")
    print(f"  -> Thời gian khởi tạo App(): {init_app_time:.2f} ms")

    # Mock profile admin
    mock_profile = {
        "id": "mock-admin-id-999",
        "full_name": "Chủ Nhà Thuốc",
        "role": "admin",
        "branch_id": None
    }

    # 2. Đo thời gian Đăng nhập & Tạo Sidebar Layout
    t0 = time.perf_counter()
    app.on_login_success(mock_profile)
    app.update_idletasks()
    login_layout_time = (time.perf_counter() - t0) * 1000
    print(f"\n[2. ĐĂNG NHẬP & DỰNG MAIN LAYOUT]:")
    print(f"  -> Thời gian chuyển từ Login sang Main Layout: {login_layout_time:.2f} ms")

    # 3. Đo thời gian khởi tạo & chuyển đổi từng Tab (Cold Start vs Cached Switch)
    tabs = ["attendance", "schedule", "approval", "reports", "settings"]
    cold_times = {}
    warm_times = {}

    print(f"\n[3. ĐO THỜI GIAN CHUYỂN TAB (TAB SWITCHING LATENCY)]:")
    # Lần 1: Cold start (Tạo mới widget)
    for tab in tabs:
        t0 = time.perf_counter()
        app.show_view(tab)
        app.update_idletasks()
        dt = (time.perf_counter() - t0) * 1000
        cold_times[tab] = dt
        print(f"  -> [Cold Start] Chuyển sang '{tab}': {dt:.2f} ms")

    # Lần 2: Warm switch (Đã có trong cache)
    for tab in tabs:
        t0 = time.perf_counter()
        app.show_view(tab)
        app.update_idletasks()
        dt = (time.perf_counter() - t0) * 1000
        warm_times[tab] = dt
        print(f"  -> [Warm Switch] Chuyển sang '{tab}': {dt:.2f} ms")

    # 4. Đếm tổng số Widget và Canvas trong cây giao diện
    def count_widgets(w):
        count = 1
        canvas_count = 1 if "canvas" in w.winfo_class().lower() else 0
        for child in w.winfo_children():
            c, cv = count_widgets(child)
            count += c
            canvas_count += cv
        return count, canvas_count

    total_widgets, total_canvases = count_widgets(app)
    print(f"\n[4. THỐNG KÊ CÂY WIDGET (WIDGET TREE ANALYSIS)]:")
    print(f"  -> Tổng số Widget Tkinter đang sống trong RAM: {total_widgets}")
    print(f"  -> Tổng số Canvas phần tử đồ họa CustomTkinter: {total_canvases}")

    # 5. Đo thời gian phản hồi giả lập Resize (Simulated Window Resize Event)
    print(f"\n[5. ĐO TỐC ĐỘ XỬ LÝ RESIZE WINDOW]:")
    resize_times = []
    for w, h in [(1200, 750), (1280, 800), (1366, 768), (1240, 780)]:
        t0 = time.perf_counter()
        app.geometry(f"{w}x{h}")
        app.update_idletasks()
        dt = (time.perf_counter() - t0) * 1000
        resize_times.append(dt)
        print(f"  -> Resize sang {w}x{h}: {dt:.2f} ms")

    avg_resize = sum(resize_times) / len(resize_times)
    fps_est = 1000 / avg_resize if avg_resize > 0 else 999
    print(f"  => Thời gian trung bình 1 frame Resize: {avg_resize:.2f} ms (~{fps_est:.1f} FPS ước lượng)")

    # 6. Đo RAM cuối
    end_mem_mb = get_memory_mb()
    print(f"\n[6. MỨC ĐỘ TIÊU THỤ BỘ NHỚ RAM]:")
    print(f"  -> RAM Kết thúc: {end_mem_mb:.2f} MB (+{end_mem_mb - init_mem_mb:.2f} MB)")

    app.destroy()
    print("=" * 70)
    print("HOÀN THÀNH BỘ ĐO BENCHMARK!")
    print("=" * 70)

if __name__ == "__main__":
    run_performance_benchmark()
