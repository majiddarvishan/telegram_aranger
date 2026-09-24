import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db.auth_sessions import (
    _hash_token,
    create_session,
    delete_session,
    get_user_by_session,
)
from db.database import get_db, initialize_database
from db.users import (
    authenticate_user,
    create_user,
    hash_password,
    verify_password,
)


class UserAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_file = str(Path(self.tmp.name) / "test.db")
        initialize_database(self.db_file)

    def tearDown(self):
        self.tmp.cleanup()

    def test_hash_password_uses_salt_and_verifies(self):
        salt, digest = hash_password("correct horse battery staple")

        self.assertEqual(len(bytes.fromhex(salt)), 32)
        self.assertTrue(
            verify_password("correct horse battery staple", salt, digest)
        )
        self.assertFalse(verify_password("wrong password", salt, digest))

    def test_create_user_rejects_short_password_even_outside_ui(self):
        with self.assertRaisesRegex(ValueError, "at least 8"):
            create_user(self.db_file, "short", "1234567", "Short")

    def test_same_password_with_random_salts_produces_different_hashes(self):
        salt1, digest1 = hash_password("password123")
        salt2, digest2 = hash_password("password123")

        self.assertNotEqual(salt1, salt2)
        self.assertNotEqual(digest1, digest2)

    def test_create_and_authenticate_user_normalizes_username(self):
        self.assertTrue(create_user(self.db_file, "  Alice  ", "password123", "Alice"))

        user = authenticate_user(self.db_file, "ALICE", "password123")

        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "alice")
        self.assertEqual(user["display_name"], "Alice")

    def test_authentication_rejects_wrong_password_and_unknown_user(self):
        create_user(self.db_file, "alice", "password123", "Alice")

        self.assertIsNone(authenticate_user(self.db_file, "alice", "wrong"))
        self.assertIsNone(authenticate_user(self.db_file, "missing", "password123"))

    def test_duplicate_username_is_rejected_case_insensitively(self):
        self.assertTrue(create_user(self.db_file, "Alice", "password123", "Alice"))
        self.assertFalse(create_user(self.db_file, "alice", "anotherpass", "Other"))


class RememberSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_file = str(Path(self.tmp.name) / "test.db")
        initialize_database(self.db_file)
        create_user(self.db_file, "alice", "password123", "Alice")
        self.user = authenticate_user(self.db_file, "alice", "password123")

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_session_stores_only_token_hash_and_restores_user(self):
        token = create_session(self.db_file, self.user["id"], 7)

        conn = get_db(self.db_file)
        try:
            row = conn.execute(
                "SELECT token_hash, expires_at FROM web_sessions"
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], _hash_token(token))
        self.assertNotEqual(row[0], token)
        self.assertGreater(datetime.fromisoformat(row[1]), datetime.now(timezone.utc))

        restored = get_user_by_session(self.db_file, token)
        self.assertEqual(restored["id"], self.user["id"])
        self.assertEqual(restored["username"], "alice")

    def test_expired_session_is_rejected_and_deleted(self):
        token = create_session(self.db_file, self.user["id"], 7)

        conn = get_db(self.db_file)
        try:
            expired = datetime.now(timezone.utc) - timedelta(minutes=1)
            conn.execute(
                "UPDATE web_sessions SET expires_at=? WHERE token_hash=?",
                (expired.isoformat(), _hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

        self.assertIsNone(get_user_by_session(self.db_file, token))

        conn = get_db(self.db_file)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM web_sessions WHERE token_hash=?",
                (_hash_token(token),),
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(count, 0)

    def test_cleanup_expired_sessions_removes_expired_and_malformed_rows(self):
        from db.auth_sessions import cleanup_expired_sessions

        valid_token = create_session(self.db_file, self.user["id"], 7)
        expired_token = create_session(self.db_file, self.user["id"], 7)

        conn = get_db(self.db_file)
        try:
            conn.execute(
                "UPDATE web_sessions SET expires_at=? WHERE token_hash=?",
                (
                    (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
                    _hash_token(expired_token),
                ),
            )
            conn.execute(
                """
                INSERT INTO web_sessions(user_id, token_hash, expires_at)
                VALUES(?,?,?)
                """,
                (self.user["id"], "malformed-token-hash", "not-a-date"),
            )
            conn.commit()
        finally:
            conn.close()

        deleted = cleanup_expired_sessions(self.db_file)

        self.assertEqual(deleted, 2)
        self.assertIsNotNone(get_user_by_session(self.db_file, valid_token))
        self.assertIsNone(get_user_by_session(self.db_file, expired_token))

    def test_delete_session_revokes_token(self):
        token = create_session(self.db_file, self.user["id"], 7)

        delete_session(self.db_file, token)

        self.assertIsNone(get_user_by_session(self.db_file, token))


if __name__ == "__main__":
    unittest.main()
