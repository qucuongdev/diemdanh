import os
import sys
import argparse
import getpass
import requests
import psycopg2
from pathlib import Path
from urllib.parse import quote_plus
from core.config import SUPABASE_URL, ENV_PATH

# Đảm bảo UTF-8 cho Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def extract_project_ref(url: str) -> str:
    """Trích xuất Project Ref từ Supabase URL"""
    return url.replace("https://", "").replace("http://", "").split(".")[0]

def migrate_via_api(project_ref: str, access_token: str, sql_content: str, file_name: str) -> bool:
    """Migrate qua Supabase Management API"""
    print(f"-> Đang thực thi {file_name} qua Supabase Management API (Project: {project_ref})...")
    api_url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    headers = {
        "Authorization": f"Bearer {access_token.strip()}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(api_url, json={"query": sql_content}, headers=headers, timeout=60)
        if response.status_code in (200, 201):
            print(f"-> [THÀNH CÔNG] Đã chạy xong file {file_name} lên Supabase!")
            return True
        else:
            print(f"-> [LỖI API {response.status_code}]: {response.text}")
            return False
    except Exception as e:
        print(f"-> [LỖI GỬI API]: {e}")
        return False

def connect_to_supabase(project_ref: str, db_pass: str):
    """Kết nối tới máy chủ PostgreSQL của Supabase"""
    encoded_pass = quote_plus(db_pass)
    candidates = [
        # Máy chủ pooler chính xác của dự án (Tokyo - ap-northeast-1)
        ("Tokyo Pooler (Port 6543)", f"postgresql://postgres.{project_ref}:{encoded_pass}@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"),
        # Direct connection (Port 5432)
        ("Direct Connection (Port 5432)", f"postgresql://postgres:{encoded_pass}@db.{project_ref}.supabase.co:5432/postgres"),
        # Các pooler dự phòng
        ("Singapore Pooler 1", f"postgresql://postgres.{project_ref}:{encoded_pass}@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"),
        ("Singapore Pooler 2", f"postgresql://postgres.{project_ref}:{encoded_pass}@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"),
        ("US East Pooler", f"postgresql://postgres.{project_ref}:{encoded_pass}@aws-0-us-east-1.pooler.supabase.com:6543/postgres")
    ]

    for label, uri in candidates:
        try:
            print(f"-> Đang kết nối tới: {label}...")
            conn = psycopg2.connect(uri, connect_timeout=8)
            conn.autocommit = True
            print("   -> Kết nối thành công!")
            return conn
        except Exception as e:
            err_str = str(e).strip()
            if "password authentication failed" in err_str:
                print("   [SAI MẬT KHẨU]: Mật khẩu Database không chính xác!")
                return None
            else:
                print(f"   [Bỏ qua]: {err_str[:60]}...")

    return None

def ensure_migrations_table(conn):
    """Khởi tạo bảng theo dõi các file SQL đã chạy để không bị chạy lặp lại"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public._schema_migrations (
                    filename TEXT PRIMARY KEY,
                    executed_at TIMESTAMPTZ DEFAULT timezone('Asia/Ho_Chi_Minh', now())
                );
            """)
    except Exception as e:
        print(f"   [Cảnh báo khởi tạo bảng migration]: {e}")

def get_executed_migrations(conn) -> set:
    """Lấy danh sách các file SQL đã từng được thực thi thành công"""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM public._schema_migrations;")
            rows = cur.fetchall()
            return {r[0] for r in rows}
    except Exception:
        return set()

def record_migration(conn, filename: str):
    """Lưu vết file SQL đã chạy thành công"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public._schema_migrations (filename, executed_at)
                VALUES (%s, timezone('Asia/Ho_Chi_Minh', now()))
                ON CONFLICT (filename) DO UPDATE SET executed_at = timezone('Asia/Ho_Chi_Minh', now());
            """, (filename,))
    except Exception as e:
        print(f"   [Cảnh báo ghi log migration]: {e}")

def main():
    parser = argparse.ArgumentParser(description="Tiện ích chạy file SQL / Migrate lên Database Supabase")
    parser.add_argument("file_pos", nargs="?", default=None, help="Tên file SQL (VD: update_admin_rpc.sql)")
    parser.add_argument("-f", "--file", help="Tên file SQL cụ thể cần chạy")
    parser.add_argument("--password", help="Mật khẩu Database của Supabase")
    parser.add_argument("--token", help="Supabase Personal Access Token (sbp_...)")
    parser.add_argument("--force", action="store_true", help="Chạy lại tất cả file kể cả đã chạy trước đó")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    project_ref = extract_project_ref(SUPABASE_URL)

    target_file = args.file or args.file_pos
    specific_mode = bool(target_file)

    files_candidate = []
    if target_file:
        target_path = base_dir / target_file if not Path(target_file).is_absolute() else Path(target_file)
        if not target_path.exists():
            print(f"[LỖI] Không tìm thấy file SQL: {target_file}")
            return
        files_candidate.append(target_path)
    else:
        # Tự động phát hiện các file theo thứ tự ưu tiên
        schema_path = base_dir / "schema.sql"
        if schema_path.exists():
            files_candidate.append(schema_path)

        rpc_path = base_dir / "update_admin_rpc.sql"
        if rpc_path.exists():
            files_candidate.append(rpc_path)

        # Quét thêm thư mục migrations/ nếu có
        migrations_dir = base_dir / "migrations"
        if migrations_dir.is_dir():
            for m_file in sorted(migrations_dir.glob("*.sql")):
                if m_file not in files_candidate:
                    files_candidate.append(m_file)

    print("=" * 65)
    print("TIỆN ÍCH TỰ ĐỘNG CHẠY SQL LÊN SUPABASE (CLI WORKFLOW)")
    print(f"Dự án: {project_ref} ({SUPABASE_URL})")
    print(f"Chế độ: {'Chạy file chỉ định: ' + target_file if specific_mode else 'Tự động quét và áp dụng bản cập nhật mới'}")
    print("=" * 65)

    # 1. Thử migrate bằng Access Token nếu có
    token = args.token or os.getenv("SUPABASE_ACCESS_TOKEN")
    if token:
        all_ok = True
        for sql_file in files_candidate:
            with open(sql_file, "r", encoding="utf-8") as f:
                content = f.read()
            if not migrate_via_api(project_ref, token, content, sql_file.name):
                all_ok = False
        if all_ok:
            print("\n🎉 [HOÀN TẤT] Đã chạy toàn bộ file SQL lên Supabase thành công!")
            return

    # 2. Thử migrate bằng Database Connection
    db_pass = args.password or os.getenv("DB_PASSWORD")
    is_prompted = False
    if not db_pass:
        print("\nNhập mật khẩu Database của Supabase (mật khẩu đặt lúc tạo dự án):")
        try:
            db_pass = getpass.getpass("Mật khẩu Database: ").strip()
        except Exception:
            db_pass = input("Mật khẩu Database: ").strip()
        is_prompted = True

    if not db_pass:
        print("[HỦY BỎ] Bạn chưa nhập mật khẩu.")
        return

    conn = connect_to_supabase(project_ref, db_pass)
    if not conn:
        print("\n❌ Không thể kết nối tới cơ sở dữ liệu. Vui lòng kiểm tra lại mật khẩu.")
        return

    # Nếu vừa nhập tay thành công và chưa có trong .env, gợi ý lưu lại
    if is_prompted and ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                env_content = f.read()
            if "DB_PASSWORD=" not in env_content:
                save_choice = input("\nBạn có muốn lưu DB_PASSWORD vào .env để các lần sau không cần nhập lại? (y/N): ").strip().lower()
                if save_choice in ("y", "yes"):
                    with open(ENV_PATH, "a", encoding="utf-8") as f:
                        f.write(f"\nDB_PASSWORD={db_pass}\n")
                    print("✅ Đã lưu DB_PASSWORD vào .env! Lần sau chỉ cần chạy lệnh mà không phải gõ mật khẩu.")
        except Exception:
            pass

    ensure_migrations_table(conn)
    executed_set = get_executed_migrations(conn)

    files_to_run = []
    for f in files_candidate:
        if specific_mode or args.force or f.name not in executed_set:
            files_to_run.append(f)
        else:
            print(f"-> [BỎ QUA] {f.name} (Đã được thực thi trước đó)")

    if not files_to_run:
        print("\n✨ Tuyệt vời! Cơ sở dữ liệu đã ở trạng thái mới nhất, không có file SQL nào cần chạy thêm.")
        conn.close()
        return

    all_success = True
    for sql_file in files_to_run:
        print(f"\n-> Đang thực thi file: {sql_file.name}...")
        with open(sql_file, "r", encoding="utf-8") as f:
            sql_content = f.read()
        try:
            with conn.cursor() as cur:
                cur.execute(sql_content)
            record_migration(conn, sql_file.name)
            print(f"   ✅ [THÀNH CÔNG] File {sql_file.name} đã được áp dụng vào Database!")
        except Exception as e:
            print(f"   ❌ [LỖI SQL TRONG {sql_file.name}]: {e}")
            all_success = False

    conn.close()

    if all_success:
        print("\n" + "=" * 65)
        print("🎉 XONG! TOÀN BỘ FILE SQL ĐÃ ĐƯỢC CHẠY THÀNH CÔNG LÊN DATABASE.")
        print("   - Cơ sở dữ liệu và các hàm quản trị đã sẵn sàng 100%.")
        print("   - Bạn có thể mở app và tạo tài khoản nhân viên ngay!")
        print("=" * 65)

if __name__ == "__main__":
    main()
