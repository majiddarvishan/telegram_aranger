import tempfile
import unittest
from pathlib import Path

from db.database import get_db, initialize_database
from db.login_attempts import (
    clear_failed_logins,
    is_login_rate_limited,
    record_failed_login,
)


class LoginThrottleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_file = str(Path(self.tmp.name) / "test.db")
        initialize_database(self.db_file)

    def tearDown(self):
        self.tmp.cleanup()

    def test_failed_logins_are_normalized_and_rate_limited(self):
        for _ in range(3):
            record_failed_login(self.db_file, "  Alice  ")

        self.assertTrue(
            is_login_rate_limited(
                self.db_file,
                "alice",
                max_attempts=3,
                window_minutes=15,
            )
        )
        self.assertTrue(
            is_login_rate_limited(
                self.db_file,
                "ALICE",
                max_attempts=3,
                window_minutes=15,
            )
        )

    def test_successful_login_can_clear_failed_attempts(self):
        for _ in range(3):
            record_failed_login(self.db_file, "alice")

        clear_failed_logins(self.db_file, "Alice")

        self.assertFalse(
            is_login_rate_limited(
                self.db_file,
                "alice",
                max_attempts=3,
                window_minutes=15,
            )
        )

    def test_old_attempts_are_removed_from_window(self):
        record_failed_login(self.db_file, "alice")

        conn = get_db(self.db_file)
        try:
            conn.execute(
                """
                UPDATE web_login_attempts
                SET attempted_at='2000-01-01T00:00:00+00:00'
                WHERE username='alice'
                """
            )
            conn.commit()
        finally:
            conn.close()

        self.assertFalse(
            is_login_rate_limited(
                self.db_file,
                "alice",
                max_attempts=1,
                window_minutes=15,
            )
        )

        conn = get_db(self.db_file)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM web_login_attempts"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
