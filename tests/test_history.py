import asyncio
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from services.telegram_service import _history


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
