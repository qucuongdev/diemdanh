import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import psutil
from unittest.mock import MagicMock

# Ensure mock Supabase to avoid network jitter in GUI benchmark
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

ADMIN_PROFILE = {
    "id": "00000000-0000-0000-0000-000000000001",
    "full_name": "Admin Chuỗi",
    "role": "admin",
    "branch_id": "b1",
    "branches": {"name": "Tổng bộ"}
}

def benchmark_pyside6():
    print("\n" + "="*50)
    print("▶ CHẠY BENCHMARK PYSIDE6 REAL APP...")
    print("="*50)

    from PySide6.QtWidgets import QApplication
    from main_qt import MainWindow
    from core.qt_worker import QtWorker

    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Đo thời gian khởi tạo & Login
    t0 = time.perf_counter()
    window = MainWindow()
    window.on_login_success(ADMIN_PROFILE)
    app.processEvents()
    init_time_ms = (time.perf_counter() - t0) * 1000

    # 2. Đo thời gian chuyển Tab (20 lần chuyển qua lại giữa 5 tab)
    tabs = ["attendance", "schedule", "approval", "reports", "settings"]
    t0_tabs = time.perf_counter()
    tab_switches = 20
    for i in range(tab_switches):
        tab_name = tabs[i % len(tabs)]
        window.main_app_widget.show_view(tab_name)
        app.processEvents()
    total_tab_time = (time.perf_counter() - t0_tabs) * 1000
    avg_tab_time = total_tab_time / tab_switches

    # 3. Đo hiệu năng Resize cửa sổ (30 khung hình)
    resize_frames = 30
    t0_resize = time.perf_counter()
    for i in range(resize_frames):
        w = 1100 + (i % 2) * 200
        h = 700 + (i % 2) * 150
        window.resize(w, h)
        app.processEvents()
    total_resize_time = (time.perf_counter() - t0_resize) * 1000
    avg_resize_frame_ms = total_resize_time / resize_frames
    fps_resize = 1000.0 / avg_resize_frame_ms if avg_resize_frame_ms > 0 else 0

    # 4. Đo Event Loop Latency (Jitter)
    jitter_samples = []
    last_tick = time.perf_counter()
    from PySide6.QtCore import QTimer
    timer = QTimer()
    timer.setInterval(10)
    def on_tick():
        nonlocal last_tick
        now = time.perf_counter()
        delta_ms = (now - last_tick) * 1000
        jitter_samples.append(abs(delta_ms - 10))
        last_tick = now
        if len(jitter_samples) >= 30:
            timer.stop()
    timer.timeout.connect(on_tick)
    last_tick = time.perf_counter()
    timer.start()
    while timer.isActive():
        app.processEvents()
        time.sleep(0.001)

    avg_jitter = sum(jitter_samples) / len(jitter_samples) if jitter_samples else 0

    # 5. Mức dùng RAM
    proc = psutil.Process(os.getpid())
    ram_mb = proc.memory_info().rss / (1024 * 1024)

    QtWorker.wait_all(2000)
    window.close()
    app.processEvents()

    return {
        "framework": "PySide6 (Qt 6)",
        "init_ms": round(init_time_ms, 2),
        "tab_switch_avg_ms": round(avg_tab_time, 2),
        "resize_frame_ms": round(avg_resize_frame_ms, 2),
        "resize_fps": round(fps_resize, 1),
        "event_loop_jitter_ms": round(avg_jitter, 2),
        "ram_mb": round(ram_mb, 1)
    }

def benchmark_customtkinter():
    print("\n" + "="*50)
    print("▶ CHẠY BENCHMARK CUSTOMTKINTER REAL APP...")
    print("="*50)

    import customtkinter as ctk
    from main import App

    # 1. Đo thời gian khởi tạo & Login
    t0 = time.perf_counter()
    app = App()
    app.on_login_success(ADMIN_PROFILE)
    app.update()
    init_time_ms = (time.perf_counter() - t0) * 1000

    # 2. Đo thời gian chuyển Tab (20 lần chuyển qua lại giữa 5 tab)
    tabs = ["attendance", "schedule", "approval", "reports", "settings"]
    t0_tabs = time.perf_counter()
    tab_switches = 20
    for i in range(tab_switches):
        tab_name = tabs[i % len(tabs)]
        app.show_view(tab_name)
        app.update()
    total_tab_time = (time.perf_counter() - t0_tabs) * 1000
    avg_tab_time = total_tab_time / tab_switches

    # 3. Đo hiệu năng Resize cửa sổ (30 khung hình)
    resize_frames = 30
    t0_resize = time.perf_counter()
    for i in range(resize_frames):
        w = 1100 + (i % 2) * 200
        h = 700 + (i % 2) * 150
        app.geometry(f"{w}x{h}")
        app.update()
    total_resize_time = (time.perf_counter() - t0_resize) * 1000
    avg_resize_frame_ms = total_resize_time / resize_frames
    fps_resize = 1000.0 / avg_resize_frame_ms if avg_resize_frame_ms > 0 else 0

    # 4. Đo Event Loop Latency (Jitter)
    jitter_samples = []
    last_tick = time.perf_counter()
    def on_tick():
        nonlocal last_tick
        now = time.perf_counter()
        delta_ms = (now - last_tick) * 1000
        jitter_samples.append(abs(delta_ms - 10))
        last_tick = now
        if len(jitter_samples) < 30:
            app.after(10, on_tick)
    last_tick = time.perf_counter()
    app.after(10, on_tick)
    while len(jitter_samples) < 30:
        app.update()
        time.sleep(0.001)

    avg_jitter = sum(jitter_samples) / len(jitter_samples) if jitter_samples else 0

    # 5. Mức dùng RAM
    proc = psutil.Process(os.getpid())
    ram_mb = proc.memory_info().rss / (1024 * 1024)

    app.destroy()

    return {
        "framework": "CustomTkinter 6.0",
        "init_ms": round(init_time_ms, 2),
        "tab_switch_avg_ms": round(avg_tab_time, 2),
        "resize_frame_ms": round(avg_resize_frame_ms, 2),
        "resize_fps": round(fps_resize, 1),
        "event_loop_jitter_ms": round(avg_jitter, 2),
        "ram_mb": round(ram_mb, 1)
    }

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"

    if mode == "ctk":
        res = benchmark_customtkinter()
        print(f"RESULT_CTK:{res}")
    elif mode == "qt":
        res = benchmark_pyside6()
        print(f"RESULT_QT:{res}")
    else:
        # Chạy trong 2 process riêng để không làm ảnh hưởng RAM và memory của nhau
        import subprocess
        import json

        cmd_ctk = [sys.executable, "bench_real_app.py", "ctk"]
        p_ctk = subprocess.run(cmd_ctk, capture_output=True, text=True, encoding="utf-8")
        ctk_out = p_ctk.stdout

        cmd_qt = [sys.executable, "bench_real_app.py", "qt"]
        p_qt = subprocess.run(cmd_qt, capture_output=True, text=True, encoding="utf-8")
        qt_out = p_qt.stdout

        ctk_res = {}
        qt_res = {}
        for line in ctk_out.splitlines():
            if line.startswith("RESULT_CTK:"):
                ctk_res = eval(line.replace("RESULT_CTK:", ""))
        for line in qt_out.splitlines():
            if line.startswith("RESULT_QT:"):
                qt_res = eval(line.replace("RESULT_QT:", ""))

        print("\n" + "="*70)
        print("          BÁO CÁO KẾT QUẢ BENCHMARK THỰC TẾ ỨNG DỤNG")
        print("="*70)
        print(f"{'Tiêu chí đánh giá':<28} | {'CustomTkinter':<18} | {'PySide6 (Qt6)':<18} | {'Cải thiện':<10}")
        print("-"*70)
        
        # Init
        imp_init = round(ctk_res.get('init_ms', 1) / max(qt_res.get('init_ms', 1), 0.01), 1)
        print(f"{'Khởi tạo & Login (ms)':<28} | {ctk_res.get('init_ms'):<18} | {qt_res.get('init_ms'):<18} | {imp_init}x nhanh hơn")

        # Tab switch
        imp_tab = round(ctk_res.get('tab_switch_avg_ms', 1) / max(qt_res.get('tab_switch_avg_ms', 1), 0.01), 1)
        print(f"{'Chuyển Tab trung bình (ms)':<28} | {ctk_res.get('tab_switch_avg_ms'):<18} | {qt_res.get('tab_switch_avg_ms'):<18} | {imp_tab}x nhanh hơn")

        # Resize latency
        imp_resize = round(ctk_res.get('resize_frame_ms', 1) / max(qt_res.get('resize_frame_ms', 1), 0.01), 1)
        print(f"{'Độ trễ Resize / khung hình':<28} | {ctk_res.get('resize_frame_ms')} ms/khung       | {qt_res.get('resize_frame_ms')} ms/khung       | {imp_resize}x mượt hơn")

        # Resize FPS
        print(f"{'Tốc độ vẽ Resize (FPS)':<28} | {ctk_res.get('resize_fps')} FPS             | {qt_res.get('resize_fps')} FPS             | +{round(qt_res.get('resize_fps', 0) - ctk_res.get('resize_fps', 0), 1)} FPS")

        # Event loop jitter
        imp_jitter = round(ctk_res.get('event_loop_jitter_ms', 1) / max(qt_res.get('event_loop_jitter_ms', 1), 0.01), 1)
        print(f"{'Độ trễ Event Loop (Jitter)':<28} | {ctk_res.get('event_loop_jitter_ms')} ms            | {qt_res.get('event_loop_jitter_ms')} ms            | {imp_jitter}x nhạy hơn")

        # RAM
        print(f"{'Mức chiếm dụng RAM (MB)':<28} | {ctk_res.get('ram_mb')} MB            | {qt_res.get('ram_mb')} MB            |")
        print("="*70)
