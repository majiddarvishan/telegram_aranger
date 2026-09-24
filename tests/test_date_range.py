import unittest
from datetime import date, datetime

from pyrogram import utils as pyrogram_utils

from utils.date_range import bounds


class DateRangeTimezoneTests(unittest.TestCase):
    def test_bounds_are_naive_server_local_datetimes(self):
        start, end = bounds(date(2026, 9, 24), date(2026, 9, 24))

        self.assertIsNone(start.tzinfo)
        self.assertIsNone(end.tzinfo)
        self.assertEqual(start, datetime(2026, 9, 24, 0, 0, 0))
        self.assertEqual(
            end,
            datetime(2026, 9, 24, 23, 59, 59, 999999),
        )

    def test_pyrogram_timestamp_roundtrip_matches_selected_local_day(self):
        selected_date = date(2026, 9, 24)
        start, end = bounds(selected_date, selected_date)
        local_noon = datetime(2026, 9, 24, 12, 0, 0)

        timestamp = pyrogram_utils.datetime_to_timestamp(local_noon)
        message_date = pyrogram_utils.timestamp_to_datetime(timestamp)

        self.assertEqual(message_date, local_noon)
        self.assertLessEqual(start, message_date)
        self.assertLessEqual(message_date, end)

    def test_history_offset_end_roundtrip_preserves_local_bound_second(self):
        _, end = bounds(date(2026, 9, 24), date(2026, 9, 24))

        # Telegram timestamps have second precision. Pyrogram's conversion
        # therefore drops only the microsecond portion of time.max.
        timestamp = pyrogram_utils.datetime_to_timestamp(end)
        roundtrip = pyrogram_utils.timestamp_to_datetime(timestamp)

        self.assertEqual(
            roundtrip,
            datetime(2026, 9, 24, 23, 59, 59),
        )


if __name__ == "__main__":
    unittest.main()
