import asyncio
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import services.telegram_service as telegram_service
from services.telegram_service import (
    _history,
    _history_with_peer_recovery,
    _latest_history,
)


class FakeHistoryClient:
    def __init__(self, messages):
        self.messages = list(messages)
        self.calls = []

    async def get_chat_history(self, chat_id, limit=0, offset_date=None):
        self.calls.append(
            {
                "chat_id": chat_id,
                "limit": limit,
                "offset_date": offset_date,
            }
        )
        for message in self.messages:
            yield message


def make_message(message_id, when, text):
    return SimpleNamespace(
        id=message_id,
        date=when,
        text=text,
        caption=None,
        photo=None,
        video=None,
        animation=None,
        document=None,
        audio=None,
        voice=None,
        video_note=None,
    )


class TelegramHistoryTests(unittest.TestCase):
    def test_history_starts_from_requested_end_date_and_filters_range(self):
        start = datetime(2026, 9, 20, 0, 0, 0)
        end = datetime(2026, 9, 20, 23, 59, 59)
        messages = [
            make_message(5, end + timedelta(hours=1), "too new"),
            make_message(4, datetime(2026, 9, 20, 20, 0), "inside 2"),
            make_message(3, datetime(2026, 9, 20, 10, 0), "inside 1"),
            make_message(2, start - timedelta(seconds=1), "too old"),
            make_message(1, start - timedelta(days=1), "never needed"),
        ]
        client = FakeHistoryClient(messages)

        result = asyncio.run(
            _history(
                chat_id=-100,
                start_dt=start,
                end_dt=end,
                limit=100,
                client=client,
            )
        )

        self.assertEqual([item["id"] for item in result], [4, 3])
        self.assertEqual(
            client.calls,
            [{"chat_id": -100, "limit": 0, "offset_date": end}],
        )

    def test_history_limit_applies_to_messages_inside_requested_range(self):
        start = datetime(2026, 9, 20, 0, 0, 0)
        end = datetime(2026, 9, 20, 23, 59, 59)
        messages = [
            make_message(5, datetime(2026, 9, 20, 20, 0), "five"),
            make_message(4, datetime(2026, 9, 20, 19, 0), "four"),
            make_message(3, datetime(2026, 9, 20, 18, 0), "three"),
        ]
        client = FakeHistoryClient(messages)

        result = asyncio.run(
            _history(
                chat_id=-100,
                start_dt=start,
                end_dt=end,
                limit=2,
                client=client,
            )
        )

        self.assertEqual([item["id"] for item in result], [5, 4])

    def test_latest_history_uses_bounded_newest_message_fetch(self):
        messages = [
            make_message(
                3,
                datetime(2026, 9, 18, 12, 0),
                "latest",
            ),
            make_message(
                2,
                datetime(2026, 9, 17, 12, 0),
                "older",
            ),
        ]
        client = FakeHistoryClient(messages)

        result = asyncio.run(
            _latest_history(
                chat_id=-100,
                limit=25,
                client=client,
            )
        )

        self.assertEqual([item["id"] for item in result], [3, 2])
        self.assertEqual(
            client.calls,
            [
                {
                    "chat_id": -100,
                    "limit": 25,
                    "offset_date": None,
                }
            ],
        )

    def test_peer_warm_prefers_username_without_dialog_refresh(self):
        class Client:
            def __init__(self):
                self.get_chat_calls = []
                self.dialog_calls = 0
                self.resolve_calls = []

            async def get_chat(self, username):
                self.get_chat_calls.append(username)
                return object()

            async def get_dialogs(self, limit=0):
                self.dialog_calls += 1
                if False:
                    yield None

            async def resolve_peer(self, chat_id):
                self.resolve_calls.append(chat_id)
                return object()

        client = Client()

        asyncio.run(
            telegram_service._warm_peer_for_history(
                client,
                -1003075722346,
                username="cached_channel",
                dialog_limit=100,
            )
        )

        self.assertEqual(
            client.get_chat_calls,
            ["cached_channel"],
        )
        self.assertEqual(client.dialog_calls, 0)
        self.assertEqual(client.resolve_calls, [])

    def test_peer_warm_falls_back_to_bounded_dialog_refresh(self):
        class Client:
            def __init__(self):
                self.requested_limit = None
                self.resolve_calls = []

            async def get_dialogs(self, limit=0):
                self.requested_limit = limit
                yield object()

            async def resolve_peer(self, chat_id):
                self.resolve_calls.append(chat_id)
                return object()

        client = Client()

        asyncio.run(
            telegram_service._warm_peer_for_history(
                client,
                -1003075722346,
                username="",
                dialog_limit=100,
            )
        )

        self.assertEqual(client.requested_limit, 100)
        self.assertEqual(
            client.resolve_calls,
            [-1003075722346],
        )

    def test_peer_id_invalid_is_recovered_once_then_history_retried(self):
        class FakePeerIdInvalid(Exception):
            pass

        recovered = [{"id": 99}]

        with (
            patch.object(
                telegram_service,
                "PeerIdInvalid",
                FakePeerIdInvalid,
            ),
            patch.object(
                telegram_service,
                "_history",
                new=AsyncMock(
                    side_effect=[
                        FakePeerIdInvalid(),
                        recovered,
                    ]
                ),
            ) as history_call,
            patch.object(
                telegram_service,
                "_warm_peer_for_history",
                new=AsyncMock(),
            ) as warm_peer,
        ):
            result = asyncio.run(
                _history_with_peer_recovery(
                    client=object(),
                    chat_id=-1003075722346,
                    start_dt=datetime(2026, 9, 20),
                    end_dt=datetime(2026, 9, 21),
                    limit=100,
                    peer_username="cached_channel",
                    dialog_limit=100,
                )
            )

        self.assertEqual(result, recovered)
        self.assertEqual(history_call.await_count, 2)
        warm_peer.assert_awaited_once_with(
            unittest.mock.ANY,
            -1003075722346,
            username="cached_channel",
            dialog_limit=100,
        )

    def test_history_supports_unlimited_results_when_limit_is_zero(self):
        start = datetime(2026, 9, 20, 0, 0, 0)
        end = datetime(2026, 9, 20, 23, 59, 59)
        messages = [
            make_message(index, datetime(2026, 9, 20, 12, 0), str(index))
            for index in range(150, 0, -1)
        ]
        client = FakeHistoryClient(messages)

        result = asyncio.run(
            _history(
                chat_id=-100,
                start_dt=start,
                end_dt=end,
                limit=0,
                client=client,
            )
        )

        self.assertEqual(len(result), 150)


if __name__ == "__main__":
    unittest.main()
