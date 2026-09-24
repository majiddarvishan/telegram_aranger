import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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


def make_media(
    *,
    file_name=None,
    mime_type=None,
    file_size=12345,
    width=640,
    height=480,
    duration=12,
):
    return SimpleNamespace(
        file_id="file-id",
        file_unique_id="unique-id",
        file_name=file_name,
        mime_type=mime_type,
        file_size=file_size,
        width=width,
        height=height,
        duration=duration,
    )


class FakeClient:
    def __init__(self, message, fail_download=False):
        self.message = message
        self.fail_download = fail_download
        self.download_count = 0

    async def get_messages(self, chat_id, message_ids):
        return self.message

    async def download_media(
        self,
        message,
        file_name,
        in_memory=False,
        progress=None,
    ):
        self.download_count += 1
        if self.fail_download:
            return None
        if progress:
            await progress(5, 10)
            await progress(10, 10)
        path = Path(file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video-data")
        return str(path)


class TelegramMediaMetadataTests(unittest.TestCase):
    def test_detects_every_supported_media_type(self):
        cases = {
            "photo": (None, "image/jpeg"),
            "video": (None, "video/mp4"),
            "animation": ("image/gif", "image/gif"),
            "document": ("application/pdf", "application/pdf"),
            "audio": ("audio/mpeg", "audio/mpeg"),
            "voice": (None, "audio/ogg"),
            "video_note": (None, "video/mp4"),
        }

        for media_type, (provided_mime, expected_mime) in cases.items():
            with self.subTest(media_type=media_type):
                media = make_media(
                    file_name=f"{media_type}.bin",
                    mime_type=provided_mime,
                )
                message = make_message(media_type=media_type, media=media)

                metadata = _media_metadata(message)

                self.assertIsNotNone(metadata)
                self.assertEqual(metadata["type"], media_type)
                self.assertEqual(metadata["mime_type"], expected_mime)
                self.assertEqual(metadata["file_id"], "file-id")
                self.assertEqual(metadata["file_unique_id"], "unique-id")

    def test_metadata_mapping_preserves_common_fields(self):
        video = make_media(
            file_name="My Clip.mp4",
            mime_type="video/mp4",
            file_size=12345,
            width=1920,
            height=1080,
            duration=42,
        )
        message = make_message(caption="caption", media_type="video", media=video)

        metadata = _media_metadata(message)

        self.assertEqual(
            metadata,
            {
                "type": "video",
                "file_id": "file-id",
                "file_unique_id": "unique-id",
                "file_name": "My Clip.mp4",
                "mime_type": "video/mp4",
                "file_size": 12345,
                "width": 1920,
                "height": 1080,
                "duration": 42,
            },
        )

    def test_returns_none_when_message_has_no_supported_media(self):
        message = make_message(text="plain text")

        self.assertIsNone(_media_metadata(message))

    def test_message_text_prefers_text_then_caption_then_media_label(self):
        photo = make_media(mime_type=None)

        text_message = make_message(
            text="message text",
            caption="caption",
            media_type="photo",
            media=photo,
        )
        caption_message = make_message(
            caption="caption",
            media_type="photo",
            media=photo,
        )
        media_only_message = make_message(media_type="photo", media=photo)
        empty_message = make_message()

        self.assertEqual(
            _message_text(text_message, _media_metadata(text_message)),
            "message text",
        )
        self.assertEqual(
            _message_text(caption_message, _media_metadata(caption_message)),
            "caption",
        )
        self.assertEqual(
            _message_text(media_only_message, _media_metadata(media_only_message)),
            "[Photo]",
        )
        self.assertEqual(_message_text(empty_message, None), "[Message]")


class TelegramMediaDownloadTests(unittest.TestCase):
    def test_download_is_lazy_and_reuses_fresh_cache(self):
        video = make_media(
            file_name="My Clip.mp4",
            mime_type="video/mp4",
            file_size=10,
            width=1280,
            height=720,
            duration=5,
        )
        message = make_message(media_type="video", media=video)
        client = FakeClient(message)

        with tempfile.TemporaryDirectory() as tmp:
            first = asyncio.run(
                _download_media(
                    client=client,
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
                    client=client,
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

    def test_truncated_cached_file_is_deleted_and_downloaded_again(self):
        video = make_media(
            file_name="clip.mp4",
            mime_type="video/mp4",
            file_size=10,
        )
        client = FakeClient(make_message(media_type="video", media=video))

        with tempfile.TemporaryDirectory() as tmp:
            first = asyncio.run(
                _download_media(
                    client=client,
                    chat_id=-100,
                    message_id=10,
                    account_id=1,
                    cache_root=tmp,
                    cache_ttl_hours=24,
                    cache_max_mb=100,
                    max_megabytes=10,
                )
            )
            Path(first["path"]).write_bytes(b"broken")

            second = asyncio.run(
                _download_media(
                    client=client,
                    chat_id=-100,
                    message_id=10,
                    account_id=1,
                    cache_root=tmp,
                    cache_ttl_hours=24,
                    cache_max_mb=100,
                    max_megabytes=10,
                )
            )
            recovered_bytes = Path(second["path"]).read_bytes()

        self.assertEqual(client.download_count, 2)
        self.assertFalse(second["cached"])
        self.assertEqual(recovered_bytes, b"video-data")

    def test_force_download_bypasses_valid_cache(self):
        video = make_media(
            file_name="clip.mp4",
            mime_type="video/mp4",
            file_size=10,
        )
        client = FakeClient(make_message(media_type="video", media=video))

        with tempfile.TemporaryDirectory() as tmp:
            first = asyncio.run(
                _download_media(
                    client=client,
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
                    client=client,
                    chat_id=-100,
                    message_id=10,
                    account_id=1,
                    cache_root=tmp,
                    cache_ttl_hours=24,
                    cache_max_mb=100,
                    max_megabytes=10,
                    force_download=True,
                )
            )

        self.assertEqual(client.download_count, 2)
        self.assertFalse(first["cached"])
        self.assertFalse(second["cached"])

    def test_download_reports_byte_progress(self):
        video = make_media(
            file_name="clip.mp4",
            mime_type="video/mp4",
            file_size=10,
        )
        client = FakeClient(make_message(media_type="video", media=video))
        updates = []

        async def progress(current, total):
            updates.append((current, total))

        with tempfile.TemporaryDirectory() as tmp:
            asyncio.run(
                _download_media(
                    client=client,
                    chat_id=-100,
                    message_id=10,
                    account_id=1,
                    cache_root=tmp,
                    cache_ttl_hours=24,
                    cache_max_mb=100,
                    max_megabytes=10,
                    progress_callback=progress,
                )
            )

        self.assertEqual(updates, [(5, 10), (10, 10)])

    def test_download_rejects_media_over_configured_limit(self):
        video = make_media(
            file_name="large.mp4",
            mime_type="video/mp4",
            file_size=25 * 1024 * 1024,
            width=1280,
            height=720,
            duration=5,
        )
        client = FakeClient(make_message(media_type="video", media=video))

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "too large"):
                asyncio.run(
                    _download_media(
                        client=client,
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
        video = make_media(
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

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "did not complete"):
                asyncio.run(
                    _download_media(
                        client=client,
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
