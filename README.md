# Chạy app trên Windows bằng Git Bash

Phiên bản app: **1.0.0**.

## 1. Cài trên máy mới

- Cài [Git for Windows](https://git-scm.com/install/windows) để có Git Bash.
- Cài [Python 3.12.10](https://www.python.org/downloads/release/python-31210/), chọn **Windows installer (64-bit)** và tích **Add python.exe to PATH** khi cài.
- Chép mã nguồn vào `D:\Work\Tool\diemdanh`, rồi mở Git Bash mới.

## 2. Cài thư viện lần đầu

```bash
cd /d/Work/Tool/diemdanh
python --version
python -m pip install -r requirements.txt
```

## 3. Cấu hình kết nối lần đầu

```bash
[ -f .env ] || cp .env.example .env
notepad .env
```

Điền `SUPABASE_URL` và `SUPABASE_KEY` (public/anon key) do quản trị viên cung cấp, lưu rồi đóng Notepad.

## 4. Chạy app

```bash
python main.py
```

Những lần sau chỉ cần:

```bash
cd /d/Work/Tool/diemdanh
python main.py
```

Nút **Giao diện sáng/tối** có ở màn đăng nhập và thanh bên, tự lưu lựa chọn. Giờ và thời lượng hiển thị theo `hh:mm` (369 phút = `06:09`).

Nếu mã nguồn nằm ở thư mục khác, thay đường dẫn trong lệnh `cd`. Nếu báo máy chủ cần cập nhật, làm theo [DEPLOYMENT.md](DEPLOYMENT.md).

## Cập nhật database một lần (quản trị viên)

Sau khi xem xét migration và sao lưu đúng database, chạy trong thư mục dự án:

```bash
python -m pip install -r requirements-admin.txt && python migrate.py --all-pending --apply
```

Công cụ lấy project từ `SUPABASE_URL` trong `.env` và chỉ hỏi **mật khẩu database Supabase** (ẩn khi nhập). Lệnh này áp dụng migration thật. Nếu mạng chỉ có IPv4, xem cách cấu hình Session pooler trong [DEPLOYMENT.md](DEPLOYMENT.md).
