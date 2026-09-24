import unittest

from config.settings import Settings


class SettingsDefaultsTests(unittest.TestCase):
    def test_default_message_scroll_height_is_large_desktop_size(self):
        settings = Settings(
            api_id=1,
            api_hash="hash",
            session_encryption_key="key",
        )

        self.assertEqual(settings.message_scroll_height, 620)


if __name__ == "__main__":
    unittest.main()
