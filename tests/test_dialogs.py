import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pyrogram import raw

from db.database import initialize_database
from db.dialogs import (
    cache_has_peer_metadata,
    load_dialogs,
    load_peer_records,
    replace_dialogs,
)
from db.telegram_accounts import save_account
from db.users import authenticate_user, create_user
from services.telegram_service import _dialogs, _hydrate_peer_cache
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

    async def get_me(self):
        return SimpleNamespace(
            id=1001,
            username="alice_tg",
        )

    async def resolve_peer(self, chat_id):
        if chat_id == 1001:
            return raw.types.InputPeerUser(
                user_id=1001,
                access_hash=555001,
            )
        return raw.types.InputPeerChat(chat_id=abs(chat_id))


class DialogServiceTests(unittest.TestCase):
    def test_dialog_limit_is_passed_to_pyrogram_and_peer_is_captured(self):
        client = FakeDialogClient()

        result = asyncio.run(_dialogs(client, 100))

        self.assertEqual(client.requested_limit, 100)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 1001)
        self.assertEqual(result[0]["title"], "Saved Messages")
        self.assertEqual(result[0]["type"], "private")
        self.assertEqual(result[0]["peer_type"], "user")
        self.assertEqual(result[1]["id"], -100)
        self.assertEqual(result[1]["title"], "Test Group")
        self.assertEqual(result[1]["peer_type"], "group")
        self.assertEqual(result[1]["peer_access_hash"], 0)

    def test_channel_access_hash_is_captured_for_persistence(self):
        class ChannelClient:
            async def get_dialogs(self, limit=0):
                chat_type = SimpleNamespace(value="channel")
                chat = SimpleNamespace(
                    id=-1001234567890,
                    title="News",
                    type=chat_type,
                    username="news",
                    first_name=None,
                    last_name=None,
                )
                yield SimpleNamespace(chat=chat)

            async def get_me(self):
                return SimpleNamespace(
                    id=1001,
                    username="alice_tg",
                )

            async def resolve_peer(self, chat_id):
                if chat_id == 1001:
                    return raw.types.InputPeerUser(
                        user_id=1001,
                        access_hash=555001,
                    )
                return raw.types.InputPeerChannel(
                    channel_id=1234567890,
                    access_hash=987654321,
                )

        result = asyncio.run(_dialogs(ChannelClient(), 100))

        channel = next(
            item for item in result
            if item["id"] == -1001234567890
        )
        self.assertEqual(channel["peer_type"], "channel")
        self.assertEqual(
            channel["peer_access_hash"],
            987654321,
        )

    def test_peer_cache_hydration_updates_pyrogram_storage(self):
        records = [
            (-1001234567890, 987654321, "channel", "news", ""),
            (-42, 0, "group", "", ""),
        ]
        client = SimpleNamespace(
            storage=SimpleNamespace(update_peers=AsyncMock())
        )

        asyncio.run(_hydrate_peer_cache(client, records))

        client.storage.update_peers.assert_awaited_once_with(records)

    def test_empty_peer_cache_does_not_touch_storage(self):
        client = SimpleNamespace(
            storage=SimpleNamespace(update_peers=AsyncMock())
        )

        asyncio.run(_hydrate_peer_cache(client, []))

        client.storage.update_peers.assert_not_awaited()


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

    @staticmethod
    def _group_dialog(chat_id=-100, title="Group"):
        return {
            "id": chat_id,
            "title": title,
            "type": "group",
            "username": "",
            "peer_access_hash": 0,
            "peer_type": "group",
        }

    @staticmethod
    def _channel_dialog(
        chat_id=-1001234567890,
        title="Channel",
        username="channel",
        access_hash=987654321,
    ):
        return {
            "id": chat_id,
            "title": title,
            "type": "channel",
            "username": username,
            "peer_access_hash": access_hash,
            "peer_type": "channel",
        }

    def test_latest_dialog_snapshot_is_loaded_in_position_order(self):
        replace_dialogs(
            self.db_file,
            self.account_id,
            [
                self._group_dialog(-100, "First"),
                self._channel_dialog(-100200, "Second", "second", 12345),
            ],
        )

        self.assertEqual(
            [item["id"] for item in load_dialogs(self.db_file, self.account_id)],
            [-100, -100200],
        )

        time.sleep(0.001)
        replace_dialogs(
            self.db_file,
            self.account_id,
            [
                self._channel_dialog(
                    -100200,
                    "Second Updated",
                    "second",
                    12345,
                )
            ],
        )

        latest = load_dialogs(self.db_file, self.account_id)
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["id"], -100200)
        self.assertEqual(latest[0]["title"], "Second Updated")
        self.assertEqual(latest[0]["peer_access_hash"], 12345)
        self.assertEqual(latest[0]["peer_type"], "channel")

    def test_peer_records_are_storage_compatible(self):
        replace_dialogs(
            self.db_file,
            self.account_id,
            [
                self._channel_dialog(
                    -1001234567890,
                    "News",
                    "news",
                    987654321,
                ),
                self._group_dialog(-42, "Group"),
            ],
        )

        self.assertEqual(
            load_peer_records(self.db_file, self.account_id),
            [
                (
                    -1001234567890,
                    987654321,
                    "channel",
                    "news",
                    "",
                ),
                (-42, 0, "group", "", ""),
            ],
        )

    def test_peer_metadata_completeness_requires_access_hash_for_channels(self):
        self.assertTrue(
            cache_has_peer_metadata(
                [self._group_dialog(), self._channel_dialog()]
            )
        )
        self.assertFalse(
            cache_has_peer_metadata(
                [
                    {
                        **self._channel_dialog(),
                        "peer_access_hash": None,
                    }
                ]
            )
        )
        self.assertFalse(
            cache_has_peer_metadata(
                [
                    {
                        "id": -100,
                        "title": "Legacy",
                        "type": "group",
                        "username": "",
                    }
                ]
            )
        )

    def test_ui_uses_peer_aware_cached_dialogs_without_network_call(self):
        cached = [self._group_dialog(title="Cached")]
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

    def test_legacy_cache_without_peer_metadata_is_refreshed_once(self):
        cached = [
            {
                "id": -100,
                "title": "Legacy",
                "type": "group",
                "username": "",
                "peer_access_hash": None,
                "peer_type": "",
            }
        ]
        fresh = [self._group_dialog(title="Fresh")]
        settings = SimpleNamespace(
            db_file=self.db_file,
            telegram_dialog_limit=100,
        )

        with (
            patch("ui.main.load_cached_dialogs", return_value=cached),
            patch(
                "ui.main.get_dialogs",
                return_value=fresh,
            ) as network_get_dialogs,
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

    def test_peer_aware_cache_without_saved_messages_is_refreshed_once(self):
        cached = [self._group_dialog(title="Cached")]
        saved = {
            "id": 1001,
            "title": "Saved Messages",
            "type": "private",
            "username": "alice_tg",
            "peer_access_hash": 555001,
            "peer_type": "user",
        }
        fresh = [saved, self._group_dialog(title="Fresh")]
        settings = SimpleNamespace(
            db_file=self.db_file,
            telegram_dialog_limit=100,
        )

        with (
            patch("ui.main.load_cached_dialogs", return_value=cached),
            patch(
                "ui.main.get_dialogs",
                return_value=fresh,
            ) as network_get_dialogs,
            patch("ui.main.replace_dialogs") as cache_replace,
        ):
            result, warning = _load_or_refresh_dialogs(
                settings,
                self.account_id,
                self_chat_id=1001,
            )

        self.assertEqual(result, fresh)
        self.assertIsNone(warning)
        network_get_dialogs.assert_called_once_with(100)
        cache_replace.assert_called_once_with(
            self.db_file,
            self.account_id,
            fresh,
        )

    def test_peer_aware_cache_with_saved_messages_avoids_network(self):
        saved = {
            "id": 1001,
            "title": "Saved Messages",
            "type": "private",
            "username": "alice_tg",
            "peer_access_hash": 555001,
            "peer_type": "user",
        }
        cached = [saved, self._group_dialog(title="Cached")]
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
                self_chat_id=1001,
            )

        self.assertEqual(result, cached)
        self.assertIsNone(warning)
        network_get_dialogs.assert_not_called()

    def test_cache_miss_fetches_only_configured_dialog_limit(self):
        fresh = [self._group_dialog(title="Fresh")]
        settings = SimpleNamespace(
            db_file=self.db_file,
            telegram_dialog_limit=100,
        )

        with (
            patch("ui.main.load_cached_dialogs", return_value=[]),
            patch(
                "ui.main.get_dialogs",
                return_value=fresh,
            ) as network_get_dialogs,
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
        cached = [self._group_dialog(title="Cached")]
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
