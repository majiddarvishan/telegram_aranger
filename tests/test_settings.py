import os
import unittest
from unittest.mock import patch

from config.settings import Settings, _env_path_list


class SettingsDefaultsTests(unittest.TestCase):
    def test_default_message_scroll_height_is_large_desktop_size(self):
        settings = Settings(
            api_id=1,
            api_hash="hash",
            session_encryption_key="key",
        )

        self.assertEqual(settings.message_scroll_height, 620)
        self.assertEqual(settings.telegram_dialog_limit, 100)
        self.assertEqual(settings.youtube_download_roots, ())

    def test_youtube_download_roots_use_host_path_separator(self):
        value = os.pathsep.join(("first-root", "second-root"))
        with patch.dict(os.environ, {"YOUTUBE_DOWNLOAD_ROOTS": value}, clear=False):
            self.assertEqual(
                _env_path_list("YOUTUBE_DOWNLOAD_ROOTS"),
                ("first-root", "second-root"),
            )


if __name__ == "__main__":
    unittest.main()
