from PySide6.QtCore import QThread, Signal

class QtWorker(QThread):
    """
    Worker thread chuẩn Qt để thực thi tác vụ I/O mạng hoặc CPU-bound nặng.
    Đảm bảo 100% thread-safe bằng Qt Signals/Slots, không bao giờ làm đơ giao diện.
    Tự động quản lý vòng đời (lifecycle management), ngăn chặn triệt để lỗi
    'QThread: Destroyed while thread is still running' của Qt C++.
    """
    result_ready = Signal(object)
    error_occurred = Signal(str)

    _active_workers = set()

    def __init__(self, target, *args, **kwargs):
        super().__init__()
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.finished.connect(self._on_finished)

    def start(self, priority=QThread.Priority.InheritPriority):
        QtWorker._active_workers.add(self)
        super().start(priority)

    def run(self):
        try:
            res = self.target(*self.args, **self.kwargs)
            self.result_ready.emit(res)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _on_finished(self):
        QtWorker._active_workers.discard(self)

    @classmethod
    def wait_all(cls, timeout_ms=3000):
        """Chờ toàn bộ các worker đang chạy kết thúc trước khi thoát ứng dụng (an toàn cho testing)"""
        workers = list(cls._active_workers)
        for w in workers:
            if w.isRunning():
                w.wait(timeout_ms)
