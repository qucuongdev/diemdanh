import sys
import os
import time
import json
import ctypes
from ctypes import wintypes
import subprocess

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

def get_ram_mb():
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

# ==============================================================================
# 1. BENCHMARK TKINTER GỐC (STANDARD TKINTER + TTK)
# ==============================================================================
def bench_tkinter():
    import tkinter as tk
    from tkinter import ttk

    t_start = time.perf_counter()
    root = tk.Tk()
    root.title("Tkinter Native Benchmark")
    root.geometry("1280x800")
    root.minsize(1000, 600)

    # 1. Sidebar (5 nút)
    sidebar = tk.Frame(root, width=200, bg="#2A2A2A")
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    for i in range(5):
        btn = tk.Button(sidebar, text=f"Nav Button {i+1}", bg="#3A3A3A", fg="white", bd=0, height=2)
        btn.pack(fill="x", padx=10, pady=5)

    # 2. Main Tab View (Notebook)
    notebook = ttk.Notebook(root)
    notebook.pack(side="right", fill="both", expand=True)

    # Tab 1: Grid View (42 ô, 4 widgets mỗi ô = 168 widgets)
    tab1 = tk.Frame(notebook)
    notebook.add(tab1, text="Tab 1: Grid (42 cards)")

    canvas1 = tk.Canvas(tab1)
    scrollbar1 = ttk.Scrollbar(tab1, orient="vertical", command=canvas1.yview)
    scroll_frame1 = tk.Frame(canvas1)
    scroll_frame1.bind("<Configure>", lambda e: canvas1.configure(scrollregion=canvas1.bbox("all")))
    canvas1.create_window((0, 0), window=scroll_frame1, anchor="nw")
    canvas1.configure(yscrollcommand=scrollbar1.set)
    canvas1.pack(side="left", fill="both", expand=True)
    scrollbar1.pack(side="right", fill="y")

    for idx in range(42):
        row = idx // 7
        col = idx % 7
        card = tk.LabelFrame(scroll_frame1, text=f"Day {idx+1}", width=140, height=120)
        card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        card.pack_propagate(False)
        tk.Label(card, text=f"Ca Sáng {idx+1}", font=("Arial", 9, "bold")).pack(anchor="w", padx=4, pady=2)
        tk.Label(card, text="08:00 - 16:00", font=("Arial", 8), fg="gray").pack(anchor="w", padx=4)
        btn_box = tk.Frame(card)
        btn_box.pack(fill="x", padx=4, pady=4)
        tk.Button(btn_box, text="Duyệt", font=("Arial", 8), width=6).pack(side="left")
        tk.Button(btn_box, text="Hủy", font=("Arial", 8), width=6).pack(side="right")

    # Tab 2: List View (50 rows x 5 widgets = 250 widgets)
    tab2 = tk.Frame(notebook)
    notebook.add(tab2, text="Tab 2: List (50 rows)")

    canvas2 = tk.Canvas(tab2)
    scrollbar2 = ttk.Scrollbar(tab2, orient="vertical", command=canvas2.yview)
    scroll_frame2 = tk.Frame(canvas2)
    scroll_frame2.bind("<Configure>", lambda e: canvas2.configure(scrollregion=canvas2.bbox("all")))
    canvas2.create_window((0, 0), window=scroll_frame2, anchor="nw")
    canvas2.configure(yscrollcommand=scrollbar2.set)
    canvas2.pack(side="left", fill="both", expand=True)
    scrollbar2.pack(side="right", fill="y")

    for i in range(50):
        r = tk.Frame(scroll_frame2, bd=1, relief="solid")
        r.pack(fill="x", padx=10, pady=3)
        tk.Checkbutton(r).pack(side="left", padx=5)
        tk.Label(r, text=f"Nhân viên Dược sĩ #{i+1:02d}", font=("Arial", 10, "bold"), width=25, anchor="w").pack(side="left", padx=5)
        tk.Label(r, text="Đang trong ca", fg="green", width=15).pack(side="left", padx=5)
        tk.Button(r, text="Xem chi tiết", width=10).pack(side="right", padx=5, pady=4)
        tk.Button(r, text="Sửa", width=6).pack(side="right", padx=5)

    # Tab 3: Form View (10 fields + buttons)
    tab3 = tk.Frame(notebook)
    notebook.add(tab3, text="Tab 3: Form (10 fields)")
    for i in range(10):
        frow = tk.Frame(tab3)
        frow.pack(fill="x", padx=30, pady=6)
        tk.Label(frow, text=f"Trường thông tin #{i+1}:", width=20, anchor="w").pack(side="left")
        tk.Entry(frow, width=40).pack(side="left", padx=10)
    btn_row = tk.Frame(tab3)
    btn_row.pack(fill="x", padx=30, pady=20)
    tk.Button(btn_row, text="Lưu", width=12, bg="#28A745", fg="white").pack(side="left", padx=5)
    tk.Button(btn_row, text="Hủy", width=12).pack(side="left", padx=5)

    root.update_idletasks()
    init_time_ms = (time.perf_counter() - t_start) * 1000

    # Test 1: Window Resizing (30 steps simulating mouse resize drag)
    resize_times = []
    for step in range(30):
        w = 1200 + step * 5
        h = 750 + step * 3
        t0 = time.perf_counter()
        root.geometry(f"{w}x{h}")
        root.update()
        dt = (time.perf_counter() - t0) * 1000
        resize_times.append(dt)

    # Test 2: Tab Switching (30 switches)
    tab_switch_times = []
    tabs = [tab1, tab2, tab3]
    for cycle in range(10):
        for idx, tab_widget in enumerate(tabs):
            t0 = time.perf_counter()
            notebook.select(tab_widget)
            root.update()
            dt = (time.perf_counter() - t0) * 1000
            tab_switch_times.append(dt)

    # Test 3: Event Loop Latency (20 timer callbacks at 10ms target)
    timer_latencies = []
    last_tick = [time.perf_counter()]
    def tick(count):
        now = time.perf_counter()
        dt = (now - last_tick[0]) * 1000
        jitter = abs(dt - 10.0)
        timer_latencies.append(jitter)
        last_tick[0] = now
        if count < 20:
            root.after(10, lambda: tick(count + 1))
        else:
            root.quit()

    root.after(10, lambda: tick(1))
    root.mainloop()

    ram_mb = get_ram_mb()
    root.destroy()

    avg_resize = sum(resize_times) / len(resize_times)
    max_resize = max(resize_times)
    avg_tab = sum(tab_switch_times) / len(tab_switch_times)
    max_tab = max(tab_switch_times)
    avg_loop_jitter = sum(timer_latencies) / len(timer_latencies) if timer_latencies else 0

    return {
        "framework": "Tkinter Gốc (Standard + ttk)",
        "init_time_ms": round(init_time_ms, 2),
        "avg_resize_ms": round(avg_resize, 2),
        "max_resize_ms": round(max_resize, 2),
        "fps_resize": round(1000 / avg_resize, 1) if avg_resize > 0 else 0,
        "avg_tab_switch_ms": round(avg_tab, 2),
        "max_tab_switch_ms": round(max_tab, 2),
        "event_loop_jitter_ms": round(avg_loop_jitter, 2),
        "ram_working_set_mb": round(ram_mb, 2)
    }

# ==============================================================================
# 2. BENCHMARK CUSTOMTKINTER (CTK 6.0.0)
# ==============================================================================
def bench_customtkinter():
    import customtkinter as ctk

    t_start = time.perf_counter()
    root = ctk.CTk()
    root.title("CustomTkinter Benchmark")
    root.geometry("1280x800")
    root.minsize(1000, 600)

    # 1. Sidebar (5 nút)
    sidebar = ctk.CTkFrame(root, width=200, corner_radius=0)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    for i in range(5):
        btn = ctk.CTkButton(sidebar, text=f"Nav Button {i+1}", height=38)
        btn.pack(fill="x", padx=10, pady=5)

    # 2. Main Tab View
    tabview = ctk.CTkTabview(root, corner_radius=8)
    tabview.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    t1 = tabview.add("Tab 1: Grid (42 cards)")
    t2 = tabview.add("Tab 2: List (50 rows)")
    t3 = tabview.add("Tab 3: Form (10 fields)")

    # Tab 1: Grid View (42 cards)
    scroll1 = ctk.CTkScrollableFrame(t1, fg_color="transparent")
    scroll1.pack(fill="both", expand=True)

    for idx in range(42):
        row = idx // 7
        col = idx % 7
        card = ctk.CTkFrame(scroll1, width=140, height=120, corner_radius=6)
        card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        card.pack_propagate(False)
        ctk.CTkLabel(card, text=f"Ca Sáng {idx+1}", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=6, pady=(4, 1))
        ctk.CTkLabel(card, text="08:00 - 16:00", font=ctk.CTkFont(size=9), text_color="gray").pack(anchor="w", padx=6)
        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(fill="x", padx=4, pady=4)
        ctk.CTkButton(btn_box, text="Duyệt", width=55, height=24, font=ctk.CTkFont(size=9)).pack(side="left")
        ctk.CTkButton(btn_box, text="Hủy", width=55, height=24, fg_color="#DC3545", hover_color="#C82333", font=ctk.CTkFont(size=9)).pack(side="right")

    # Tab 2: List View (50 rows)
    scroll2 = ctk.CTkScrollableFrame(t2, fg_color="transparent")
    scroll2.pack(fill="both", expand=True)

    for i in range(50):
        r = ctk.CTkFrame(scroll2, corner_radius=6)
        r.pack(fill="x", padx=10, pady=3)
        ctk.CTkCheckBox(r, text="").pack(side="left", padx=5)
        ctk.CTkLabel(r, text=f"Nhân viên Dược sĩ #{i+1:02d}", font=ctk.CTkFont(size=12, weight="bold"), width=180, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(r, text="Đang trong ca", text_color="#28A745", width=120).pack(side="left", padx=5)
        ctk.CTkButton(r, text="Xem", width=70, height=28).pack(side="right", padx=5, pady=4)
        ctk.CTkButton(r, text="Sửa", width=60, height=28).pack(side="right", padx=5)

    # Tab 3: Form View (10 fields)
    for i in range(10):
        frow = ctk.CTkFrame(t3, fg_color="transparent")
        frow.pack(fill="x", padx=30, pady=6)
        ctk.CTkLabel(frow, text=f"Trường thông tin #{i+1}:", width=150, anchor="w").pack(side="left")
        ctk.CTkEntry(frow, width=280).pack(side="left", padx=10)
    btn_row = ctk.CTkFrame(t3, fg_color="transparent")
    btn_row.pack(fill="x", padx=30, pady=20)
    ctk.CTkButton(btn_row, text="Lưu", width=100, fg_color="#28A745", hover_color="#218838").pack(side="left", padx=5)
    ctk.CTkButton(btn_row, text="Hủy", width=100, fg_color="gray").pack(side="left", padx=5)

    root.update_idletasks()
    init_time_ms = (time.perf_counter() - t_start) * 1000

    # Test 1: Window Resizing (30 steps)
    resize_times = []
    for step in range(30):
        w = 1200 + step * 5
        h = 750 + step * 3
        t0 = time.perf_counter()
        root.geometry(f"{w}x{h}")
        root.update()
        dt = (time.perf_counter() - t0) * 1000
        resize_times.append(dt)

    # Test 2: Tab Switching (30 switches)
    tab_switch_times = []
    tab_names = ["Tab 1: Grid (42 cards)", "Tab 2: List (50 rows)", "Tab 3: Form (10 fields)"]
    for cycle in range(10):
        for name in tab_names:
            t0 = time.perf_counter()
            tabview.set(name)
            root.update()
            dt = (time.perf_counter() - t0) * 1000
            tab_switch_times.append(dt)

    # Test 3: Event Loop Latency (20 timer callbacks at 10ms target)
    timer_latencies = []
    last_tick = [time.perf_counter()]
    def tick(count):
        now = time.perf_counter()
        dt = (now - last_tick[0]) * 1000
        jitter = abs(dt - 10.0)
        timer_latencies.append(jitter)
        last_tick[0] = now
        if count < 20:
            root.after(10, lambda: tick(count + 1))
        else:
            root.quit()

    root.after(10, lambda: tick(1))
    root.mainloop()

    ram_mb = get_ram_mb()
    root.destroy()

    avg_resize = sum(resize_times) / len(resize_times)
    max_resize = max(resize_times)
    avg_tab = sum(tab_switch_times) / len(tab_switch_times)
    max_tab = max(tab_switch_times)
    avg_loop_jitter = sum(timer_latencies) / len(timer_latencies) if timer_latencies else 0

    return {
        "framework": "CustomTkinter 6.0.0",
        "init_time_ms": round(init_time_ms, 2),
        "avg_resize_ms": round(avg_resize, 2),
        "max_resize_ms": round(max_resize, 2),
        "fps_resize": round(1000 / avg_resize, 1) if avg_resize > 0 else 0,
        "avg_tab_switch_ms": round(avg_tab, 2),
        "max_tab_switch_ms": round(max_tab, 2),
        "event_loop_jitter_ms": round(avg_loop_jitter, 2),
        "ram_working_set_mb": round(ram_mb, 2)
    }

# ==============================================================================
# 3. BENCHMARK PYSIDE6 (QT 6 C++ RUNTIME)
# ==============================================================================
def bench_pyside6():
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QPushButton, QLabel, QLineEdit, QCheckBox,
        QScrollArea, QTabWidget, QFrame
    )
    from PySide6.QtCore import QTimer

    t_start = time.perf_counter()
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("PySide6 (Qt 6) Benchmark")
    window.resize(1280, 800)
    window.setMinimumSize(1000, 600)

    central = QWidget()
    window.setCentralWidget(central)
    root_layout = QHBoxLayout(central)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    # 1. Sidebar (5 buttons)
    sidebar = QWidget()
    sidebar.setFixedWidth(200)
    sidebar.setStyleSheet("background-color: #2A2A2A;")
    sb_layout = QVBoxLayout(sidebar)
    sb_layout.setContentsMargins(10, 10, 10, 10)
    sb_layout.setSpacing(8)

    for i in range(5):
        btn = QPushButton(f"Nav Button {i+1}")
        btn.setStyleSheet("background-color: #3A3A3A; color: white; padding: 8px; border-radius: 4px;")
        sb_layout.addWidget(btn)
    sb_layout.addStretch()
    root_layout.addWidget(sidebar)

    # 2. Main Tab View
    tabs = QTabWidget()
    root_layout.addWidget(tabs)

    # Tab 1: Grid (42 cards)
    tab1 = QWidget()
    t1_layout = QVBoxLayout(tab1)
    scroll1 = QScrollArea()
    scroll1.setWidgetResizable(True)
    scroll1_content = QWidget()
    grid1 = QGridLayout(scroll1_content)
    grid1.setSpacing(8)

    for idx in range(42):
        row = idx // 7
        col = idx % 7
        card = QFrame()
        card.setFixedSize(140, 120)
        card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #DCDCDC; border-radius: 6px;")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(6, 6, 6, 6)
        c_layout.setSpacing(2)

        lbl_t = QLabel(f"Ca Sáng {idx+1}")
        lbl_t.setStyleSheet("font-weight: bold; border: none;")
        c_layout.addWidget(lbl_t)

        lbl_s = QLabel("08:00 - 16:00")
        lbl_s.setStyleSheet("color: gray; border: none;")
        c_layout.addWidget(lbl_s)

        btn_box = QWidget()
        btn_box.setStyleSheet("border: none;")
        b_layout = QHBoxLayout(btn_box)
        b_layout.setContentsMargins(0, 4, 0, 0)
        b_layout.setSpacing(4)
        b1 = QPushButton("Duyệt")
        b1.setStyleSheet("background-color: #0D6EFD; color: white; border-radius: 3px;")
        b2 = QPushButton("Hủy")
        b2.setStyleSheet("background-color: #DC3545; color: white; border-radius: 3px;")
        b_layout.addWidget(b1)
        b_layout.addWidget(b2)
        c_layout.addWidget(btn_box)

        grid1.addWidget(card, row, col)

    scroll1.setWidget(scroll1_content)
    t1_layout.addWidget(scroll1)
    tabs.addTab(tab1, "Tab 1: Grid (42 cards)")

    # Tab 2: List (50 rows)
    tab2 = QWidget()
    t2_layout = QVBoxLayout(tab2)
    scroll2 = QScrollArea()
    scroll2.setWidgetResizable(True)
    scroll2_content = QWidget()
    list_layout = QVBoxLayout(scroll2_content)
    list_layout.setSpacing(6)

    for i in range(50):
        r = QFrame()
        r.setStyleSheet("background-color: white; border: 1px solid #E0E0E0; border-radius: 4px;")
        r_layout = QHBoxLayout(r)
        r_layout.setContentsMargins(10, 6, 10, 6)

        chk = QCheckBox()
        r_layout.addWidget(chk)

        lbl_name = QLabel(f"Nhân viên Dược sĩ #{i+1:02d}")
        lbl_name.setStyleSheet("font-weight: bold; border: none;")
        lbl_name.setFixedWidth(180)
        r_layout.addWidget(lbl_name)

        lbl_st = QLabel("Đang trong ca")
        lbl_st.setStyleSheet("color: #28A745; border: none;")
        lbl_st.setFixedWidth(120)
        r_layout.addWidget(lbl_st)

        r_layout.addStretch()

        b_edit = QPushButton("Sửa")
        b_edit.setFixedSize(60, 28)
        b_view = QPushButton("Xem")
        b_view.setFixedSize(70, 28)
        r_layout.addWidget(b_edit)
        r_layout.addWidget(b_view)

        list_layout.addWidget(r)

    scroll2.setWidget(scroll2_content)
    t2_layout.addWidget(scroll2)
    tabs.addTab(tab2, "Tab 2: List (50 rows)")

    # Tab 3: Form (10 fields)
    tab3 = QWidget()
    form_layout = QVBoxLayout(tab3)
    form_layout.setContentsMargins(30, 20, 30, 20)
    for i in range(10):
        frow = QWidget()
        fr_layout = QHBoxLayout(frow)
        fr_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(f"Trường thông tin #{i+1}:")
        lbl.setFixedWidth(150)
        ent = QLineEdit()
        ent.setFixedWidth(280)
        fr_layout.addWidget(lbl)
        fr_layout.addWidget(ent)
        fr_layout.addStretch()
        form_layout.addWidget(frow)

    b_row = QWidget()
    br_layout = QHBoxLayout(b_row)
    br_layout.setContentsMargins(0, 10, 0, 0)
    b_save = QPushButton("Lưu")
    b_save.setFixedSize(100, 32)
    b_save.setStyleSheet("background-color: #28A745; color: white;")
    b_cancel = QPushButton("Hủy")
    b_cancel.setFixedSize(100, 32)
    br_layout.addWidget(b_save)
    br_layout.addWidget(b_cancel)
    br_layout.addStretch()
    form_layout.addWidget(b_row)
    form_layout.addStretch()
    tabs.addTab(tab3, "Tab 3: Form (10 fields)")

    window.show()
    app.processEvents()
    init_time_ms = (time.perf_counter() - t_start) * 1000

    # Test 1: Window Resizing (30 steps)
    resize_times = []
    for step in range(30):
        w = 1200 + step * 5
        h = 750 + step * 3
        t0 = time.perf_counter()
        window.resize(w, h)
        app.processEvents()
        dt = (time.perf_counter() - t0) * 1000
        resize_times.append(dt)

    # Test 2: Tab Switching (30 switches)
    tab_switch_times = []
    for cycle in range(10):
        for idx in range(3):
            t0 = time.perf_counter()
            tabs.setCurrentIndex(idx)
            app.processEvents()
            dt = (time.perf_counter() - t0) * 1000
            tab_switch_times.append(dt)

    # Test 3: Event Loop Latency (20 timer callbacks at 10ms target)
    timer_latencies = []
    last_tick = [time.perf_counter()]
    timer = QTimer()

    tick_count = [0]
    def on_timer_tick():
        now = time.perf_counter()
        dt = (now - last_tick[0]) * 1000
        jitter = abs(dt - 10.0)
        timer_latencies.append(jitter)
        last_tick[0] = now
        tick_count[0] += 1
        if tick_count[0] >= 20:
            timer.stop()
            app.quit()

    timer.timeout.connect(on_timer_tick)
    timer.start(10)
    app.exec()

    ram_mb = get_ram_mb()
    window.close()

    avg_resize = sum(resize_times) / len(resize_times)
    max_resize = max(resize_times)
    avg_tab = sum(tab_switch_times) / len(tab_switch_times)
    max_tab = max(tab_switch_times)
    avg_loop_jitter = sum(timer_latencies) / len(timer_latencies) if timer_latencies else 0

    return {
        "framework": "PySide6 (Qt 6.x / C++)",
        "init_time_ms": round(init_time_ms, 2),
        "avg_resize_ms": round(avg_resize, 2),
        "max_resize_ms": round(max_resize, 2),
        "fps_resize": round(1000 / avg_resize, 1) if avg_resize > 0 else 0,
        "avg_tab_switch_ms": round(avg_tab, 2),
        "max_tab_switch_ms": round(max_tab, 2),
        "event_loop_jitter_ms": round(avg_loop_jitter, 2),
        "ram_working_set_mb": round(ram_mb, 2)
    }

# ==============================================================================
# SUBPROCESS ENTRYPOINT / AGGREGATOR
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--target":
        target = sys.argv[2]
        if target == "tkinter":
            res = bench_tkinter()
        elif target == "customtkinter":
            res = bench_customtkinter()
        elif target == "pyside6":
            res = bench_pyside6()
        else:
            res = {"error": f"Unknown target: {target}"}
        print(f"BENCH_RESULT:{json.dumps(res)}")
        sys.exit(0)

    # Master Runner: Executes each in an isolated clean Python process
    print("=" * 80)
    print("BỘ BENCHMARK ĐỘC LẬP SO SÁNH HIỆU NĂNG: TKINTER vs CUSTOMTKINTER vs PYSIDE6")
    print("Cùng cấu hình máy Windows, kích thước 1280x800, ~550 widgets (Grid, List, Form)")
    print("=" * 80)

    targets = ["tkinter", "customtkinter", "pyside6"]
    results = []

    for t in targets:
        print(f"\n[+] Đang chạy kiểm thử cô lập cho: {t.upper()}...")
        cmd = [sys.executable, __file__, "--target", t]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        out = proc.stdout
        err = proc.stderr
        
        found = False
        for line in out.splitlines():
            if line.startswith("BENCH_RESULT:"):
                data = json.loads(line.replace("BENCH_RESULT:", ""))
                results.append(data)
                found = True
                break
        if not found:
            print(f"[-] Lỗi khi chạy {t}:")
            print("STDOUT:", out)
            print("STDERR:", err)

    # In bảng tổng hợp so sánh chuẩn khoa học
    print("\n" + "=" * 90)
    print(f"{'CHỈ SỐ ĐO LƯỜNG':<32} | {'TKINTER GỐC':<16} | {'CUSTOMTKINTER':<16} | {'PYSIDE6 (QT 6)':<16}")
    print("=" * 90)

    def get_val(data, key):
        return str(data.get(key, "N/A"))

    if len(results) == 3:
        tk_d, ctk_d, qt_d = results[0], results[1], results[2]
        print(f"{'1. Khởi tạo & Dựng UI (ms)':<32} | {get_val(tk_d, 'init_time_ms') + ' ms':<16} | {get_val(ctk_d, 'init_time_ms') + ' ms':<16} | {get_val(qt_d, 'init_time_ms') + ' ms':<16}")
        print(f"{'2. Tốc độ Resize TB (ms/frame)':<32} | {get_val(tk_d, 'avg_resize_ms') + ' ms':<16} | {get_val(ctk_d, 'avg_resize_ms') + ' ms':<16} | {get_val(qt_d, 'avg_resize_ms') + ' ms':<16}")
        print(f"{'3. Độ giật Resize cực đại (ms)':<32} | {get_val(tk_d, 'max_resize_ms') + ' ms':<16} | {get_val(ctk_d, 'max_resize_ms') + ' ms':<16} | {get_val(qt_d, 'max_resize_ms') + ' ms':<16}")
        print(f"{'4. Ước lượng FPS khi Resize':<32} | {get_val(tk_d, 'fps_resize') + ' FPS':<16} | {get_val(ctk_d, 'fps_resize') + ' FPS':<16} | {get_val(qt_d, 'fps_resize') + ' FPS':<16}")
        print(f"{'5. Chuyển Tab trung bình (ms)':<32} | {get_val(tk_d, 'avg_tab_switch_ms') + ' ms':<16} | {get_val(ctk_d, 'avg_tab_switch_ms') + ' ms':<16} | {get_val(qt_d, 'avg_tab_switch_ms') + ' ms':<16}")
        print(f"{'6. Chuyển Tab cực đại (Spike)':<32} | {get_val(tk_d, 'max_tab_switch_ms') + ' ms':<16} | {get_val(ctk_d, 'max_tab_switch_ms') + ' ms':<16} | {get_val(qt_d, 'max_tab_switch_ms') + ' ms':<16}")
        print(f"{'7. Event Loop Jitter/Trễ (ms)':<32} | {get_val(tk_d, 'event_loop_jitter_ms') + ' ms':<16} | {get_val(ctk_d, 'event_loop_jitter_ms') + ' ms':<16} | {get_val(qt_d, 'event_loop_jitter_ms') + ' ms':<16}")
        print(f"{'8. RAM Working Set (MB)':<32} | {get_val(tk_d, 'ram_working_set_mb') + ' MB':<16} | {get_val(ctk_d, 'ram_working_set_mb') + ' MB':<16} | {get_val(qt_d, 'ram_working_set_mb') + ' MB':<16}")
        print("=" * 90)
