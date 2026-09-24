import tempfile
import unittest
from pathlib import Path

from db.database import initialize_database
from db.tags import get_tags, save_tags
from db.telegram_accounts import delete_account, get_account, list_accounts, save_account
from db.users import authenticate_user, create_user


class TelegramAccountOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_file = str(Path(self.tmp.name) / "test.db")
        initialize_database(self.db_file)

        create_user(self.db_file, "alice", "password123", "Alice")
        create_user(self.db_file, "bob", "password123", "Bob")
        self.alice = authenticate_user(self.db_file, "alice", "password123")
        self.bob = authenticate_user(self.db_file, "bob", "password123")

    def tearDown(self):
        self.tmp.cleanup()

    def _telegram_user(self, telegram_id=1001, username="tguser"):
        return {
            "id": telegram_id,
            "phone_number": "+989120000000",
            "username": username,
            "first_name": "Telegram",
            "last_name": "User",
        }

    def test_account_is_visible_only_to_owner(self):
        account_id = save_account(
            self.db_file,
            self.alice["id"],
            self._telegram_user(),
            b"encrypted-session",
        )

        self.assertIsNotNone(
            get_account(self.db_file, self.alice["id"], account_id)
        )
        self.assertIsNone(
            get_account(self.db_file, self.bob["id"], account_id)
        )
        self.assertEqual(len(list_accounts(self.db_file, self.alice["id"])), 1)
        self.assertEqual(list_accounts(self.db_file, self.bob["id"]), [])

    def test_non_owner_cannot_delete_account_or_its_tags(self):
        account_id = save_account(
            self.db_file,
            self.alice["id"],
            self._telegram_user(),
            b"encrypted-session",
        )
        save_tags(self.db_file, account_id, -100, 42, ["private"])

        delete_account(self.db_file, self.bob["id"], account_id)

        self.assertIsNotNone(
            get_account(self.db_file, self.alice["id"], account_id)
        )
        self.assertEqual(
            get_tags(self.db_file, account_id, -100, 42),
            ["private"],
        )

    def test_save_updates_existing_account_for_same_owner(self):
        account_id = save_account(
            self.db_file,
            self.alice["id"],
            self._telegram_user(username="before"),
            b"session-1",
        )
        updated_id = save_account(
            self.db_file,
            self.alice["id"],
            self._telegram_user(username="after"),
            b"session-2",
        )

        self.assertEqual(account_id, updated_id)
        account = get_account(self.db_file, self.alice["id"], account_id)
        self.assertEqual(account["username"], "after")
        self.assertEqual(account["encrypted_session"], b"session-2")

    def test_same_telegram_identity_can_belong_to_two_web_users(self):
        alice_account = save_account(
            self.db_file,
            self.alice["id"],
            self._telegram_user(),
            b"alice-session",
        )
        bob_account = save_account(
            self.db_file,
            self.bob["id"],
            self._telegram_user(),
            b"bob-session",
        )

        self.assertNotEqual(alice_account, bob_account)
        self.assertEqual(len(list_accounts(self.db_file, self.alice["id"])), 1)
        self.assertEqual(len(list_accounts(self.db_file, self.bob["id"])), 1)


if __name__ == "__main__":
    unittest.main()
