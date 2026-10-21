"""Migration review must never import secrets or connect to a database."""

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit
import sys
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
from types import SimpleNamespace

import migrate


class MigrationReviewTests(unittest.TestCase):
    def test_apply_refuses_unrecorded_earlier_migration_before_executing_sql(self):
        connection = MagicMock()
        connection.execute.return_value.fetchone.side_effect = [None, (1,)]
        driver = SimpleNamespace(connect=MagicMock(), OperationalError=OSError)
        driver.connect.return_value.__enter__.return_value = connection
        with patch.dict(sys.modules, {"psycopg": driver}), patch("migrate.database_uri", return_value="offline"), \
             patch.object(sys, "argv", ["migrate.py", "--file", "migrations/20261020_04_qt_completion.sql", "--apply"]), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(migrate.main(), 1)
        connection.transaction.assert_not_called()
        for call in connection.execute.call_args_list:
            self.assertNotIn("CREATE OR REPLACE FUNCTION", call.args[0])

    def test_apply_skips_recorded_current_file_without_replaying_it(self):
        path = migrate.candidates("migrations/20261021_05_personnel_payroll.sql")[0]
        import hashlib
        connection = MagicMock()
        connection.execute.return_value.fetchone.return_value = (hashlib.sha256(path.read_bytes()).hexdigest(),)
        driver = SimpleNamespace(connect=MagicMock(), OperationalError=OSError)
        driver.connect.return_value.__enter__.return_value = connection
        with patch.dict(sys.modules, {"psycopg": driver}), patch("migrate.database_uri", return_value="offline"), \
             patch.object(sys, "argv", ["migrate.py", "--file", "migrations/20261021_05_personnel_payroll.sql", "--apply"]), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(migrate.main(), 0)
        connection.transaction.assert_not_called()

    def setUp(self):
        self.project_url = "https://abcdefghijklmnopqrst.supabase.co"
        env = patch.dict(os.environ, {"SUPABASE_DB_URL": "", "SUPABASE_URL": self.project_url})
        env.start()
        self.addCleanup(env.stop)
        settings = patch("migrate.dotenv_values", return_value={"SUPABASE_URL": self.project_url})
        self.settings = settings.start()
        self.addCleanup(settings.stop)

    def test_database_url_uses_environment_without_prompt(self):
        uri = "postgresql://offline:fake@localhost/offline"
        with patch.dict(os.environ, {"SUPABASE_DB_URL": uri}), patch("migrate.getpass") as prompt:
            self.assertEqual(migrate.database_uri(), uri)
        prompt.assert_not_called()

    def test_only_password_is_prompted_and_special_characters_are_encoded(self):
        password = " fake:p@ss /?#%ấ "
        output = io.StringIO()
        with patch("migrate.getpass", return_value=password) as prompt:
            with redirect_stdout(output):
                parsed = urlsplit(migrate.database_uri())
        self.assertEqual(parsed.hostname, "db.abcdefghijklmnopqrst.supabase.co")
        self.assertEqual(parsed.username, "postgres")
        self.assertEqual(unquote(parsed.password), password)
        self.assertEqual(parsed.query, "sslmode=require")
        self.assertNotIn(password, output.getvalue())
        self.assertIn("Mật khẩu database", prompt.call_args.args[0])

    def test_invalid_connection_override_is_rejected_before_password_prompt(self):
        for value in ("https://offline.supabase.co", "sb_secret_fake", "postgresql://postgres@host:invalid/db"):
            with self.subTest(value=value), patch.dict(os.environ, {"SUPABASE_DB_URL": value}):
                with patch("migrate.getpass") as prompt, self.assertRaises(ValueError):
                    migrate.database_uri()
                prompt.assert_not_called()

    def test_empty_password_is_rejected(self):
        with patch("migrate.getpass", return_value=""), self.assertRaises(ValueError):
            migrate.database_uri()

    def test_project_url_is_read_from_mocked_settings_only_when_needed(self):
        with patch.dict(os.environ, {"SUPABASE_URL": ""}), patch("migrate.getpass", return_value="fake"):
            parsed = urlsplit(migrate.database_uri())
        self.assertEqual(parsed.hostname, "db.abcdefghijklmnopqrst.supabase.co")
        self.settings.assert_called_once_with(migrate.BASE_DIR / ".env", interpolate=False)

    def test_custom_host_requires_explicit_endpoint_and_never_guesses_pooler(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "https://custom.invalid"}):
            with patch("migrate.getpass") as prompt, self.assertRaises(ValueError):
                migrate.database_uri()
            prompt.assert_not_called()

    def test_pooler_template_preserves_host_user_and_options(self):
        for template in (
            "postgresql://postgres.project:[YOUR-PASSWORD]@pooler.invalid:5432/postgres?sslmode=require",
            "postgresql://postgres.project@pooler.invalid:5432/postgres?sslmode=require",
        ):
            with self.subTest(template=template), patch.dict(os.environ, {"SUPABASE_DB_URL": template}):
                with patch("migrate.getpass", return_value="fake@password"):
                    parsed = urlsplit(migrate.database_uri())
                self.assertEqual(parsed.hostname, "pooler.invalid")
                self.assertEqual(parsed.username, "postgres.project")
                self.assertEqual(unquote(parsed.password), "fake@password")
                self.assertEqual(parsed.query, "sslmode=require")

    def test_database_url_never_falls_back_to_visible_input(self):
        with patch.dict(os.environ, {"SUPABASE_DB_URL": ""}):
            with patch("migrate.getpass", side_effect=migrate.GetPassWarning), self.assertRaises(ValueError):
                migrate.database_uri()

    def test_review_lists_ordered_migrations_without_importing_database_driver(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["migrate.py", "--all-pending"]), redirect_stdout(output):
            with patch.dict(sys.modules, {"psycopg": None}):
                self.assertEqual(migrate.main(), 0)
        rendered = output.getvalue()
        self.assertIn("No database connection made", rendered)
        self.settings.assert_not_called()
        self.assertIn("20261020_04_qt_completion.sql", rendered)
        paths = migrate.candidates(all_pending=True)
        self.assertEqual(paths, sorted(paths))

    def test_review_rejects_files_outside_project_and_non_sql(self):
        for filename in ("../outside.sql", "main.py", "missing.sql"):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                migrate.candidates(filename)

    def test_single_file_review_uses_project_root(self):
        paths = migrate.candidates("migrations/20261020_04_qt_completion.sql")
        self.assertEqual(paths, [Path(migrate.BASE_DIR) / "migrations/20261020_04_qt_completion.sql"])
