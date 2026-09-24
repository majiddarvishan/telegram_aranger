import sqlite3
import tempfile
import unittest
from pathlib import Path

from db.database import get_db, get_schema_version, initialize_database
from db.tags import (
    all_tags,
    get_tags,
    get_tags_for_messages,
    normalize_tags,
    save_tags,
)
from db.telegram_accounts import delete_account, save_account
from db.users import authenticate_user, create_user


class MessageTagIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_file = str(Path(self.tmp.name) / "test.db")
        initialize_database(self.db_file)

        create_user(self.db_file, "alice", "password123", "Alice")
        self.user = authenticate_user(self.db_file, "alice", "password123")
        self.account_id = save_account(
            self.db_file,
            self.user["id"],
            {
                "id": 1001,
                "phone_number": "+989120000000",
                "username": "tguser",
                "first_name": "Telegram",
                "last_name": "User",
            },
            b"encrypted-session",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_tag_normalization_trims_and_deduplicates(self):
        self.assertEqual(
            normalize_tags([" work ", "work", "", "important", "important "]),
            ["work", "important"],
        )

        save_tags(
            self.db_file,
            self.account_id,
            -100,
            10,
            [" work ", "work", "important"],
        )
        self.assertEqual(
            get_tags(self.db_file, self.account_id, -100, 10),
            ["work", "important"],
        )

    def test_same_message_id_in_two_chats_has_independent_tags(self):
        save_tags(self.db_file, self.account_id, -100, 42, ["work"])
        save_tags(self.db_file, self.account_id, -200, 42, ["family"])

        self.assertEqual(get_tags(self.db_file, self.account_id, -100, 42), ["work"])
        self.assertEqual(get_tags(self.db_file, self.account_id, -200, 42), ["family"])

    def test_batch_tag_lookup_returns_all_requested_messages(self):
        save_tags(self.db_file, self.account_id, -100, 41, ["one"])
        save_tags(self.db_file, self.account_id, -100, 42, ["two", "shared"])

        result = get_tags_for_messages(
            self.db_file,
            self.account_id,
            -100,
            [41, 42, 43],
        )

        self.assertEqual(result[41], ["one"])
        self.assertEqual(result[42], ["two", "shared"])
        self.assertEqual(result[43], [])

    def test_all_tags_excludes_legacy_unassigned_rows(self):
        save_tags(self.db_file, self.account_id, -100, 1, ["work", "important"])

        conn = get_db(self.db_file)
        try:
            conn.execute(
                """
                INSERT INTO message_tags(
                    telegram_account_id, chat_id, message_id, tags
                ) VALUES(?,?,?,?)
                """,
                (self.account_id, 0, 99, "legacy"),
            )
            conn.commit()
        finally:
            conn.close()

        self.assertEqual(all_tags(self.db_file, self.account_id), ["important", "work"])


class MessageTagMigrationTests(unittest.TestCase):
    def test_legacy_schema_is_migrated_without_discarding_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_file = str(Path(tmp) / "legacy.db")
            conn = sqlite3.connect(db_file)
            try:
                conn.executescript(
                    """
                    PRAGMA foreign_keys=ON;
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        password_salt TEXT NOT NULL,
                        display_name TEXT
                    );
                    CREATE TABLE telegram_accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        telegram_user_id INTEGER NOT NULL,
                        encrypted_session BLOB NOT NULL,
                        UNIQUE(user_id, telegram_user_id),
                        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                    );
                    CREATE TABLE message_tags (
                        telegram_account_id INTEGER NOT NULL,
                        message_id INTEGER NOT NULL,
                        tags TEXT,
                        PRIMARY KEY(telegram_account_id, message_id),
                        FOREIGN KEY(telegram_account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE
                    );
                    INSERT INTO users(
                        id, username, password_hash, password_salt, display_name
                    ) VALUES(1, 'alice', 'hash', 'salt', 'Alice');
                    INSERT INTO telegram_accounts(
                        id, user_id, telegram_user_id, encrypted_session
                    ) VALUES(10, 1, 1001, X'01');
                    INSERT INTO message_tags(
                        telegram_account_id, message_id, tags
                    ) VALUES(10, 42, 'legacy-tag');
                    """
                )
                conn.commit()
            finally:
                conn.close()

            initialize_database(db_file)

            conn = get_db(db_file)
            try:
                columns = {
                    row[1]
                    for row in conn.execute(
                        "PRAGMA table_info(message_tags)"
                    ).fetchall()
                }
                row = conn.execute(
                    """
                    SELECT telegram_account_id, chat_id, message_id, tags
                    FROM message_tags
                    """
                ).fetchone()
            finally:
                conn.close()

            self.assertIn("chat_id", columns)
            self.assertEqual(row, (10, 0, 42, "legacy-tag"))
            self.assertEqual(get_schema_version(db_file), 2)


if __name__ == "__main__":
    unittest.main()
