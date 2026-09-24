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
        self.assertEqual(get_schema_version(self.db_file), 3)


if __name__ == "__main__":
    unittest.main()
