import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.telegram_service import _download_media, _media_metadata, _message_text


MEDIA_ATTRS = (
    "photo",
    "video",
    "animation",
    "document",
    "audio",
    "voice",
    "video_note",
)


def make_message(*, text=None, caption=None, media_type=None, media=None):
    values = {
        "text": text,
        "caption": caption,
    }
    for name in MEDIA_ATTRS:
        values[name] = media if name == media_type else None
    return SimpleNamespace(**values)


class FakeClient:
    def __init__(self, message, fail_download=False):
        self.message = message
        self.fail_download = fail_download
        self.download_count = 0

    async def get_messages(self, chat_id, message_ids):
        return self.message

    async def download_media(self, message, file_name, in_memory=False):
        self.download_count += 1
        if self.fail_download:
            return None
        path = Path(file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video-data")
        return str(path)


class TelegramMediaTests(unittest.TestCase):
    def test_media_metadata_detects_video_and_preserves_fields(self):
        video = SimpleNamespace(
            file_id="file-id",
            file_unique_id="unique-id",
            file_name="My Clip.mp4",
            mime_type="video/mp4",
            file_size=12345,
            width=1920,
            height=1080,
            duration=42,
        )
        message = make_message(caption="caption", media_type="video", media=video)

        metadata = _media_metadata(message)

        self.assertEqual(metadata["type"], "video")
        self.assertEqual(metadata["file_name"], "My Clip.mp4")
        self.assertEqual(metadata["mime_type"], "video/mp4")
        self.assertEqual(metadata["file_size"], 12345)
        self.assertEqual(metadata["duration"], 42)
        self.assertEqual(_message_text(message, metadata), "caption")

    def test_photo_receives_default_mime_type(self):
        photo = SimpleNamespace(
            file_id="photo-id",
            file_unique_id="photo-unique",
            file_size=100,
            width=800,
            height=600,
        )
        message = make_message(media_type="photo", media=photo)

        metadata = _media_metadata(message)

        self.assertEqual(metadata["type"], "photo")
        self.assertEqual(metadata["mime_type"], "image/jpeg")
        self.assertEqual(_message_text(message, metadata), "[Photo]")

    def test_download_is_lazy_and_reuses_fresh_cache(self):
        video = SimpleNamespace(
            file_id="file-id",
            file_unique_id="unique-id",
            file_name="My Clip.mp4",
            mime_type="video/mp4",
            file_size=10,
            width=1280,
            height=720,
            duration=5,
        )
        message = make_message(media_type="video", media=video)
        client = FakeClient(message)
        runtime = SimpleNamespace(client=client)

        with tempfile.TemporaryDirectory() as tmp, patch(
            "services.telegram_service.get_runtime",
            return_value=runtime,
        ):
            first = asyncio.run(
                _download_media(
                    chat_id=-100,
                    message_id=10,
                    account_id=1,
                    cache_root=tmp,
                    cache_ttl_hours=24,
                    cache_max_mb=100,
                    max_megabytes=10,
                )
            )
            second = asyncio.run(
                _download_media(
                    chat_id=-100,
                    message_id=10,
                    account_id=1,
                    cache_root=tmp,
                    cache_ttl_hours=24,
                    cache_max_mb=100,
                    max_megabytes=10,
                )
            )

        self.assertEqual(client.download_count, 1)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(first["file_name"], "My_Clip.mp4")
        self.assertEqual(first["mime_type"], "video/mp4")

    def test_download_rejects_media_over_configured_limit(self):
        video = SimpleNamespace(
            file_id="file-id",
            file_unique_id="unique-id",
            file_name="large.mp4",
            mime_type="video/mp4",
            file_size=25 * 1024 * 1024,
            width=1280,
            height=720,
            duration=5,
        )
        client = FakeClient(make_message(media_type="video", media=video))
        runtime = SimpleNamespace(client=client)

        with tempfile.TemporaryDirectory() as tmp, patch(
            "services.telegram_service.get_runtime",
            return_value=runtime,
        ):
            with self.assertRaisesRegex(ValueError, "too large"):
                asyncio.run(
                    _download_media(
                        chat_id=-100,
                        message_id=10,
                        account_id=1,
                        cache_root=tmp,
                        cache_ttl_hours=24,
                        cache_max_mb=100,
                        max_megabytes=10,
                    )
                )

        self.assertEqual(client.download_count, 0)

    def test_failed_download_returns_clear_error(self):
        video = SimpleNamespace(
            file_id="file-id",
            file_unique_id="unique-id",
            file_name="clip.mp4",
            mime_type="video/mp4",
            file_size=10,
            width=1280,
            height=720,
            duration=5,
        )
        client = FakeClient(
            make_message(media_type="video", media=video),
            fail_download=True,
        )
        runtime = SimpleNamespace(client=client)

        with tempfile.TemporaryDirectory() as tmp, patch(
            "services.telegram_service.get_runtime",
            return_value=runtime,
        ):
            with self.assertRaisesRegex(RuntimeError, "did not complete"):
                asyncio.run(
                    _download_media(
                        chat_id=-100,
                        message_id=10,
                        account_id=1,
                        cache_root=tmp,
                        cache_ttl_hours=24,
                        cache_max_mb=100,
                        max_megabytes=10,
                    )
                )


if __name__ == "__main__":
    unittest.main()
