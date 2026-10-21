"""Explicit, transactional migrations. No backend calls without an apply flag."""

import argparse
import hashlib
import os
import re
import warnings
from getpass import getpass, GetPassWarning
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent


def database_password():
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            password = getpass("Mật khẩu database Supabase (ẩn khi nhập): ")
    except (EOFError, KeyboardInterrupt, GetPassWarning):
        raise ValueError("Không thể nhập ẩn. Thử chạy bằng winpty python migrate.py --all-pending --apply.") from None
    if not password:
        raise ValueError("Mật khẩu database không được để trống.")
    return password


def database_uri():
    """Resolve the public endpoint only in apply mode; keep passwords in memory."""
    uri = os.getenv("SUPABASE_DB_URL", "").strip()
    if not uri:
        public_url = os.getenv("SUPABASE_URL", "").strip()
        if not public_url:
            public_url = str(dotenv_values(BASE_DIR / ".env", interpolate=False).get("SUPABASE_URL") or "").strip()
        try:
            parsed_public = urlsplit(public_url)
            project = re.fullmatch(r"([a-z0-9]{20})\.supabase\.co", parsed_public.hostname or "")
        except ValueError:
            raise ValueError("SUPABASE_URL không hợp lệ.") from None
        if not project or parsed_public.scheme != "https":
            raise ValueError("Cần SUPABASE_URL chuẩn trong .env; với host riêng hoặc pooler, đặt SUPABASE_DB_URL.")
        uri = f"postgresql://postgres@db.{project[1]}.supabase.co:5432/postgres?sslmode=require"
    if not uri.startswith(("postgresql://", "postgres://")):
        raise ValueError("Cần PostgreSQL connection string đầy đủ, không phải SUPABASE_URL hoặc API key.")
    uri = uri.replace("[YOUR-PASSWORD]", "%5BYOUR-PASSWORD%5D")
    try:
        parsed = urlsplit(uri)
        if not parsed.hostname or not parsed.username or (parsed.port is not None and parsed.port <= 0):
            raise ValueError()
    except ValueError:
        raise ValueError("Địa chỉ PostgreSQL không hợp lệ. Kiểm tra SUPABASE_DB_URL.") from None
    if parsed.password and unquote(parsed.password) != "[YOUR-PASSWORD]":
        return uri
    print(f"Database: {parsed.hostname}:{parsed.port or 5432}")
    username, _, host = parsed.netloc.rpartition("@")
    username = username.split(":", 1)[0]
    password = quote(database_password(), safe="")
    return parsed._replace(netloc=f"{username}:{password}@{host}").geturl()


def candidates(filename=None, all_pending=False):
    if filename:
        path = (BASE_DIR / filename).resolve()
        if not path.is_relative_to(BASE_DIR) or path.suffix != ".sql" or not path.is_file():
            raise ValueError("Choose an existing SQL file inside this project")
        return [path]
    if all_pending:
        return sorted((BASE_DIR / "migrations").glob("*.sql"))
    raise ValueError("Specify --file or --all-pending")


def main():
    parser = argparse.ArgumentParser(description="Review or explicitly apply SQL migrations")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("-f", "--file")
    choice.add_argument("--all-pending", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Apply reviewed SQL; prompt for database password if needed")
    args = parser.parse_args()
    try:
        paths = candidates(args.file, args.all_pending)
    except ValueError as exc:
        parser.error(str(exc))
    for path in paths:
        print(f"{path.relative_to(BASE_DIR)}  sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    if not args.apply:
        print("Review only. No database connection made. Add --apply after review.")
        return 0
    try:
        import psycopg
    except ImportError:
        parser.error("Cài công cụ trước: python -m pip install -r requirements-admin.txt")
    try:
        uri = database_uri()
    except ValueError as exc:
        parser.error(str(exc))

    try:
        with psycopg.connect(uri, autocommit=True, connect_timeout=10) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS public._schema_migrations (filename text PRIMARY KEY, checksum text, executed_at timestamptz DEFAULT now())"
            )
            connection.execute("ALTER TABLE public._schema_migrations ADD COLUMN IF NOT EXISTS checksum text")
            connection.execute("ALTER TABLE public._schema_migrations ENABLE ROW LEVEL SECURITY")
            connection.execute("REVOKE ALL ON public._schema_migrations FROM anon, authenticated")
            # Serialize two deployment processes for this application.
            connection.execute("SELECT pg_advisory_lock(748293102)")
            for path in paths:
                name = str(path.relative_to(BASE_DIR)).replace(chr(92), "/")
                checksum = hashlib.sha256(path.read_bytes()).hexdigest()
                previous = connection.execute(
                    "SELECT checksum FROM public._schema_migrations WHERE filename = %s", (name,)
                ).fetchone()
                if previous:
                    if previous[0] and previous[0] != checksum:
                        raise ValueError("Applied migration changed; create a new migration instead")
                    print(f"Skip applied migration: {name}")
                    continue
                if name.startswith("migrations/") and connection.execute(
                    "SELECT 1 FROM public._schema_migrations WHERE filename LIKE 'migrations/%%' "
                    "AND filename > %s LIMIT 1", (name,)
                ).fetchone():
                    # A previous SQL Editor deployment may have no CLI history.
                    # Replaying it could replace newer functions with older versions.
                    raise ValueError("Unrecorded earlier migration; review deployment history before applying")
                # Files can also be pasted into SQL editor with their own transaction.
                sql = re.sub(r"(?m)^(BEGIN;|COMMIT;)\s*$", "", path.read_text(encoding="utf-8"))
                with connection.transaction():
                    connection.execute(sql)
                    connection.execute(
                        "INSERT INTO public._schema_migrations(filename, checksum) VALUES (%s, %s)",
                        (name, checksum),
                    )
                print(f"Applied: {name}")
        return 0
    except Exception as exc:
        print(f"Migration stopped ({type(exc).__name__}). Review database logs; credentials are not printed.")
        if isinstance(exc, psycopg.OperationalError):
            print("Kiểm tra mật khẩu và kết nối mạng. Nếu mạng không hỗ trợ IPv6, dùng Session pooler theo DEPLOYMENT.md.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
