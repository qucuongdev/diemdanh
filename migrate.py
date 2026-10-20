"""Explicit, transactional migrations. No backend calls without an apply flag."""

import argparse
import hashlib
import os
import re
from core.config import BASE_DIR


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
    parser.add_argument("--apply", action="store_true", help="Apply reviewed SQL to SUPABASE_DB_URL")
    args = parser.parse_args()
    paths = candidates(args.file, args.all_pending)
    for path in paths:
        print(f"{path.relative_to(BASE_DIR)}  sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    if not args.apply:
        print("Review only. No database connection made. Add --apply after review.")
        return 0
    uri = os.getenv("SUPABASE_DB_URL")
    if not uri:
        parser.error("SUPABASE_DB_URL is required for administrative migrations")
    import psycopg

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
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
