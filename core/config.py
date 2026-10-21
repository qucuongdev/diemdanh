import os
from pathlib import Path
from dotenv import load_dotenv

# Tìm file .env ở thư mục gốc của dự án
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

if os.getenv("ATTENDANCE_TESTING") != "1":
    load_dotenv(dotenv_path=ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

APP_NAME = "Hệ Thống Chấm Công Nhà Thuốc"
APP_VERSION = "1.0.0"
BACKEND_VERSION = 4
