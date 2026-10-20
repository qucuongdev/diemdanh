"""Bounded background tasks with queued, lifetime-aware GUI delivery."""

import logging
import time
import weakref

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from shiboken6 import isValid

ERROR_MESSAGE = "Không thể hoàn tất thao tác. Kiểm tra kết nối và thử lại."


class QtWorker(QThread):
    result_ready = Signal(object)
    error_occurred = Signal(str)
    _completed = Signal(object, bool)
    _active_workers = set()

    def __init__(self, target, *args, owner=None, **kwargs):
        super().__init__()
        self.target, self.args, self.kwargs = target, args, kwargs
        self._owner = weakref.ref(owner) if owner is not None else None
        self._completed.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        self.finished.connect(self._on_finished)

    def start(self, priority=QThread.Priority.InheritPriority):
        self._active_workers.add(self)
        super().start(priority)

    def run(self):
        try:
            self._completed.emit(self.target(*self.args, **self.kwargs), True)
        except Exception as exc:
            # Raw server errors can contain tokens or personal data.
            logging.getLogger(__name__).warning("Background task failed: %s", type(exc).__name__)
            self._completed.emit(ERROR_MESSAGE, False)

    @Slot(object, bool)
    def _deliver(self, value, success):
        if self._owner is not None:
            owner = self._owner()
            if owner is None or not isValid(owner):
                return
        if success:
            self.result_ready.emit(value)
        else:
            self.error_occurred.emit(value)

    @Slot()
    def _on_finished(self):
        self._active_workers.discard(self)
        self.target = None
        self.args, self.kwargs = (), {}
        self.deleteLater()

    @classmethod
    def wait_all(cls, timeout_ms=3000):
        deadline = time.monotonic() + timeout_ms / 1000
        for worker in list(cls._active_workers):
            if isValid(worker) and worker.isRunning():
                worker.wait(max(0, int((deadline - time.monotonic()) * 1000)))
        return not any(isValid(w) and w.isRunning() for w in cls._active_workers)

    @classmethod
    def busy(cls):
        return any(isValid(w) and w.isRunning() for w in cls._active_workers)


class TaskRunner(QObject):
    """At most one running task and one latest pending read per logical key."""

    def __init__(self, owner):
        super().__init__(owner)
        self._active = {}
        self._versions = {}
        self._pending = {}
        self._closed = False

    def invalidate(self):
        self._closed = True
        self._pending.clear()
        self._versions = {key: value + 1 for key, value in self._versions.items()}

    def cancel(self, key):
        """Discard delivery and queued replacement; never terminate a running thread."""
        self._versions[key] = self._versions.get(key, 0) + 1
        self._pending.pop(key, None)

    def submit(self, key, work, on_result, on_error, *, replace=True):
        if self._closed or (not replace and key in self._active):
            return False
        version = self._versions.get(key, 0) + 1
        self._versions[key] = version
        request = (version, work, on_result, on_error)
        if key in self._active:
            self._pending[key] = request
        else:
            self._start(key, request)
        return True

    def _start(self, key, request):
        version, work, on_result, on_error = request
        worker = QtWorker(work, owner=self)
        self._active[key] = worker

        def complete(value, success):
            self._active.pop(key, None)
            if not self._closed and self._versions.get(key) == version:
                try:
                    (on_result if success else on_error)(value)
                except Exception:
                    logging.getLogger(__name__).exception("GUI task callback failed")
            pending = self._pending.pop(key, None)
            if pending and not self._closed:
                self._start(key, pending)

        worker.result_ready.connect(lambda value: complete(value, True))
        worker.error_occurred.connect(lambda value: complete(value, False))
        worker.start()
