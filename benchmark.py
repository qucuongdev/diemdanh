"""Offline Qt table benchmark. Measures model update/layout, not FPS."""

import os

os.environ["ATTENDANCE_TESTING"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import statistics
import time
from PySide6.QtWidgets import QApplication, QWidget
from views_qt.common import TableModel, table_for
from views_qt.qt_theme import configure_application


def main():
    app = QApplication.instance() or QApplication([])
    configure_application(app)
    model = TableModel([("Nhân viên", lambda row: row["name"]), ("Trạng thái", lambda row: row["status"])])
    table = table_for(model)
    table.resize(1000, 600)
    table.show()
    app.processEvents()
    results = []
    for count in (50, 150, 1000):
        records = [{"name": f"Nhân viên {i}", "status": "Đã chấm công"} for i in range(count)]
        samples = []
        for _ in range(10):
            start = time.perf_counter()
            model.replace(records)
            app.processEvents()
            samples.append((time.perf_counter() - start) * 1000)
        results.append(
            {
                "rows": count,
                "median_update_ms": round(statistics.median(samples), 2),
                "max_update_ms": round(max(samples), 2),
                "qwidget_descendants": len(table.findChildren(QWidget)),
            }
        )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    table.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
