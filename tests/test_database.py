import tempfile
import unittest
from pathlib import Path

from db.database import get_db, get_schema_version, initialize_database


class DatabaseConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_file = str(Path(self.tmp.name) / "test.db")
        initialize_database(self.db_file)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sqlite_connection_uses_expected_concurrency_pragmas(self):
        conn = get_db(self.db_file)
        try:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(journal_mode.lower(), "wal")
        self.assertEqual(foreign_keys, 1)
        self.assertEqual(busy_timeout, 30000)
        self.assertEqual(synchronous, 1)

    def test_schema_version_is_current(self):
        self.assertEqual(get_schema_version(self.db_file), 4)

    def test_schema_v3_dialog_cache_is_migrated_with_peer_columns(self):
        legacy_db = str(Path(self.tmp.name) / "legacy-v3.db")
        conn = get_db(legacy_db)
        try:
            conn.executescript(
                """
                CREATE TABLE telegram_dialog_cache (
                    telegram_account_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    chat_type TEXT NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY(telegram_account_id, chat_id)
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

        initialize_database(legacy_db)

        conn = get_db(legacy_db)
        try:
            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(telegram_dialog_cache)"
                ).fetchall()
            }
        finally:
            conn.close()

        self.assertIn("peer_access_hash", columns)
        self.assertIn("peer_type", columns)
        self.assertEqual(get_schema_version(legacy_db), 4)


if __name__ == "__main__":
    unittest.main()
