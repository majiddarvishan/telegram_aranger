import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from db.database import initialize_database
from db.dialogs import load_dialogs, replace_dialogs
from db.telegram_accounts import save_account
from db.users import authenticate_user, create_user
from services.telegram_service import _dialogs
from ui.main import _load_or_refresh_dialogs




class FakeDialogClient:
    def __init__(self):
        self.requested_limit = None

    async def get_dialogs(self, limit=0):
        self.requested_limit = limit
        chat_type = SimpleNamespace(value="group")
        chat = SimpleNamespace(
            id=-100,
            title="Test Group",
            type=chat_type,
            username="test_group",
            first_name=None,
            last_name=None,
        )
        yield SimpleNamespace(chat=chat)


class DialogServiceTests(unittest.TestCase):
    def test_dialog_limit_is_passed_to_pyrogram(self):
        client = FakeDialogClient()

        result = asyncio.run(_dialogs(client, 100))

        self.assertEqual(client.requested_limit, 100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], -100)
        self.assertEqual(result[0]["title"], "Test Group")

class DialogCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_file = str(Path(self.tmp.name) / "test.db")
        initialize_database(self.db_file)
        create_user(self.db_file, "alice", "password123", "Alice")
        user = authenticate_user(self.db_file, "alice", "password123")
        self.account_id = save_account(
            self.db_file,
            user["id"],
            {
                "id": 1001,
                "phone_number": "+989120000000",
                "username": "alice_tg",
                "first_name": "Alice",
                "last_name": "Telegram",
            },
            b"encrypted-session",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_latest_dialog_snapshot_is_loaded_in_position_order(self):
        replace_dialogs(
            self.db_file,
            self.account_id,
            [
                {
                    "id": -100,
                    "title": "First",
                    "type": "group",
                    "username": "",
                },
                {
                    "id": -200,
                    "title": "Second",
                    "type": "channel",
                    "username": "second",
                },
            ],
        )

        self.assertEqual(
            [item["id"] for item in load_dialogs(self.db_file, self.account_id)],
            [-100, -200],
        )

        time.sleep(0.001)
        replace_dialogs(
            self.db_file,
            self.account_id,
            [
                {
                    "id": -200,
                    "title": "Second Updated",
                    "type": "channel",
                    "username": "second",
                }
            ],
        )

        latest = load_dialogs(self.db_file, self.account_id)
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["id"], -200)
        self.assertEqual(latest[0]["title"], "Second Updated")

    def test_ui_uses_cached_dialogs_without_network_call(self):
        cached = [
            {
                "id": -100,
                "title": "Cached",
                "type": "group",
                "username": "",
            }
        ]
        settings = SimpleNamespace(
            db_file=self.db_file,
            telegram_dialog_limit=100,
        )

        with (
            patch("ui.main.load_cached_dialogs", return_value=cached),
            patch("ui.main.get_dialogs") as network_get_dialogs,
        ):
            result, warning = _load_or_refresh_dialogs(
                settings,
                self.account_id,
            )

        self.assertEqual(result, cached)
        self.assertIsNone(warning)
        network_get_dialogs.assert_not_called()

    def test_cache_miss_fetches_only_configured_dialog_limit(self):
        fresh = [
            {
                "id": -100,
                "title": "Fresh",
                "type": "group",
                "username": "",
            }
        ]
        settings = SimpleNamespace(
            db_file=self.db_file,
            telegram_dialog_limit=100,
        )

        with (
            patch("ui.main.load_cached_dialogs", return_value=[]),
            patch("ui.main.get_dialogs", return_value=fresh) as network_get_dialogs,
            patch("ui.main.replace_dialogs") as cache_replace,
        ):
            result, warning = _load_or_refresh_dialogs(
                settings,
                self.account_id,
            )

        self.assertEqual(result, fresh)
        self.assertIsNone(warning)
        network_get_dialogs.assert_called_once_with(100)
        cache_replace.assert_called_once_with(
            self.db_file,
            self.account_id,
            fresh,
        )

    def test_failed_forced_refresh_falls_back_to_existing_cache(self):
        cached = [
            {
                "id": -100,
                "title": "Cached",
                "type": "group",
                "username": "",
            }
        ]
        settings = SimpleNamespace(
            db_file=self.db_file,
            telegram_dialog_limit=100,
        )

        with (
            patch("ui.main.load_cached_dialogs", return_value=cached),
            patch(
                "ui.main.get_dialogs",
                side_effect=RuntimeError("Telegram busy"),
            ),
        ):
            result, warning = _load_or_refresh_dialogs(
                settings,
                self.account_id,
                force_refresh=True,
            )

        self.assertEqual(result, cached)
        self.assertIn("showing cached chats", warning)


if __name__ == "__main__":
    unittest.main()
