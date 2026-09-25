import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.youtube_service import (
    YtDlpBackend,
    YouTubeServiceError,
    detect_ffmpeg,
    inspect_video,
    normalize_downloader_error,
    normalize_formats,
    normalize_metadata,
    normalize_subtitle_tracks,
    validate_youtube_url,
)


class FakeBackend:
    def __init__(self, metadata=None, error=None):
        self.metadata = metadata or {}
        self.error = error
        self.urls = []

    def inspect(self, url):
        self.urls.append(url)
        if self.error:
            raise self.error
        return self.metadata


class YouTubeUrlValidationTests(unittest.TestCase):
    def test_accepts_supported_single_video_shapes(self):
        cases = {
            "https://www.youtube.com/watch?v=BaW_jenozKc": "BaW_jenozKc",
            "https://youtu.be/BaW_jenozKc": "BaW_jenozKc",
            "https://youtube.com/shorts/BaW_jenozKc": "BaW_jenozKc",
            "https://youtube.com/live/BaW_jenozKc": "BaW_jenozKc",
            "https://www.youtube-nocookie.com/embed/BaW_jenozKc": "BaW_jenozKc",
        }

        for url, video_id in cases.items():
            with self.subTest(url=url):
                self.assertEqual(validate_youtube_url(url)["video_id"], video_id)

    def test_watch_url_with_playlist_parameter_is_still_one_video(self):
        result = validate_youtube_url(
            "https://www.youtube.com/watch?v=BaW_jenozKc&list=PL123"
        )
        self.assertEqual(result["video_id"], "BaW_jenozKc")

    def test_rejects_playlist_channel_and_non_youtube_urls(self):
        cases = (
            "https://www.youtube.com/playlist?list=PL123",
            "https://www.youtube.com/@example",
            "https://example.com/watch?v=BaW_jenozKc",
            "file:///tmp/video",
            "",
        )

        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(YouTubeServiceError):
                    validate_youtube_url(url)


class YouTubeMetadataNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            "id": "BaW_jenozKc",
            "title": "Test Video",
            "uploader": "Uploader",
            "channel": "Channel",
            "thumbnail": "https://img.example/thumb.jpg",
            "duration": 42.8,
            "availability": "public",
            "age_limit": 18,
            "is_live": False,
            "was_live": False,
            "live_status": "not_live",
            "formats": [
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 128,
                    "filesize": 1000,
                },
                {
                    "format_id": "137",
                    "ext": "mp4",
                    "vcodec": "avc1",
                    "acodec": "none",
                    "height": 1080,
                    "width": 1920,
                    "fps": 30,
                    "tbr": 4500,
                    "filesize_approx": 5000,
                },
                {
                    "format_id": "22",
                    "ext": "mp4",
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "height": 720,
                    "width": 1280,
                    "fps": 30,
                    "tbr": 2200,
                    "filesize": 3500,
                },
                {
                    "format_id": "storyboard",
                    "ext": "mhtml",
                    "vcodec": "none",
                    "acodec": "none",
                },
            ],
            "subtitles": {
                "en": [
                    {"ext": "vtt", "name": "English"},
                    {"ext": "srt", "name": "English"},
                ]
            },
            "automatic_captions": {
                "en": [{"ext": "vtt", "name": "English (auto)"}],
                "fa": [{"ext": "json3", "name": "Persian"}],
            },
        }

    def test_inspection_returns_ui_safe_normalized_metadata(self):
        backend = FakeBackend(self.raw)
        result = inspect_video(
            "https://www.youtube.com/watch?v=BaW_jenozKc",
            backend=backend,
        )
        self.assertEqual(
            backend.urls,
            ["https://www.youtube.com/watch?v=BaW_jenozKc"],
        )
        self.assertEqual(result["video_id"], "BaW_jenozKc")
        self.assertEqual(result["title"], "Test Video")
        self.assertEqual(result["channel"], "Channel")
        self.assertEqual(result["duration_seconds"], 42)
        self.assertEqual(result["availability"], "public")
        self.assertEqual(result["age_limit"], 18)
        self.assertFalse(result["has_drm"])
        self.assertEqual(len(result["formats"]), 3)
        self.assertEqual(len(result["subtitles"]), 3)

    def test_format_normalization_exposes_size_and_audio_video_shape(self):
        formats = normalize_formats(self.raw["formats"])
        by_id = {item["format_id"]: item for item in formats}
        self.assertNotIn("storyboard", by_id)
        self.assertTrue(by_id["137"]["has_video"])
        self.assertFalse(by_id["137"]["has_audio"])
        self.assertEqual(by_id["137"]["size_bytes"], 5000)
        self.assertTrue(by_id["137"]["size_is_estimate"])
        self.assertTrue(by_id["140"]["has_audio"])
        self.assertFalse(by_id["140"]["has_video"])
        self.assertFalse(by_id["140"]["size_is_estimate"])

    def test_quality_presets_are_simple_and_availability_aware(self):
        result = normalize_metadata(self.raw)
        presets = {item["key"]: item for item in result["quality_presets"]}
        self.assertTrue(presets["best"]["available"])
        self.assertTrue(presets["max_1080p"]["available"])
        self.assertTrue(presets["max_720p"]["available"])
        self.assertFalse(presets["max_480p"]["available"])

    def test_subtitles_keep_manual_and_automatic_sources_separate(self):
        tracks = normalize_subtitle_tracks(
            self.raw["subtitles"],
            self.raw["automatic_captions"],
        )
        manual_en = next(
            item
            for item in tracks
            if item["language"] == "en" and item["source"] == "manual"
        )
        auto_en = next(
            item
            for item in tracks
            if item["language"] == "en" and item["source"] == "automatic"
        )
        self.assertEqual(manual_en["preferred_format"], "srt")
        self.assertEqual(manual_en["formats"], ["vtt", "srt"])
        self.assertEqual(auto_en["preferred_format"], "vtt")

    def test_thumbnail_falls_back_to_last_available_thumbnail(self):
        raw = dict(self.raw)
        raw["thumbnail"] = None
        raw["thumbnails"] = [
            {"url": "https://img.example/small.jpg"},
            {"url": "https://img.example/large.jpg"},
        ]
        result = normalize_metadata(raw)
        self.assertEqual(result["thumbnail"], "https://img.example/large.jpg")

    def test_rejects_metadata_for_a_different_video_id(self):
        raw = dict(self.raw)
        raw["id"] = "Different123"
        backend = FakeBackend(raw)

        with self.assertRaises(YouTubeServiceError) as caught:
            inspect_video(
                "https://www.youtube.com/watch?v=BaW_jenozKc",
                backend=backend,
            )

        self.assertEqual(
            caught.exception.code,
            "metadata_video_mismatch",
        )

    def test_rejects_playlist_metadata_even_if_url_contains_video(self):
        backend = FakeBackend(
            {"_type": "playlist", "id": "PL123", "entries": []}
        )
        with self.assertRaisesRegex(YouTubeServiceError, "one YouTube video"):
            inspect_video(
                "https://www.youtube.com/watch?v=BaW_jenozKc",
                backend=backend,
            )


class YtDlpBackendTests(unittest.TestCase):
    def test_backend_inspects_without_downloading_media(self):
        seen = {}

        class FakeYoutubeDL:
            def __init__(self, options):
                seen["options"] = options

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, url, download):
                seen["url"] = url
                seen["download"] = download
                return {"id": "BaW_jenozKc", "title": "Test"}

        fake_module = SimpleNamespace(YoutubeDL=FakeYoutubeDL)
        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            result = YtDlpBackend().inspect(
                "https://www.youtube.com/watch?v=BaW_jenozKc"
            )
        self.assertEqual(result["id"], "BaW_jenozKc")
        self.assertFalse(seen["download"])
        self.assertTrue(seen["options"]["skip_download"])
        self.assertTrue(seen["options"]["noplaylist"])
        self.assertTrue(seen["options"]["quiet"])
        self.assertTrue(seen["options"]["no_warnings"])

    def test_backend_rejects_v1_forbidden_access_options(self):
        forbidden_cases = (
            {"cookiefile": "/tmp/cookies.txt"},
            {"cookiesfrombrowser": ("chrome",)},
            {"username": "user"},
            {"password": "secret"},
            {"proxy": "socks5://127.0.0.1:1080"},
            {"geo_bypass": True},
            {"geo_bypass_country": "US"},
            {"http_headers": {"Cookie": "secret"}},
        )

        for options in forbidden_cases:
            with self.subTest(options=list(options)):
                with self.assertRaises(YouTubeServiceError) as caught:
                    YtDlpBackend(extra_options=options)

                self.assertEqual(
                    caught.exception.code,
                    "downloader_option_not_allowed",
                )
                self.assertTrue(caught.exception.access_restricted)

    def test_backend_extra_options_cannot_override_inspect_invariants(self):
        seen = {}

        class FakeYoutubeDL:
            def __init__(self, options):
                seen["options"] = options

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, _url, download):
                seen["download"] = download
                return {"id": "BaW_jenozKc", "title": "Test"}

        fake_module = SimpleNamespace(YoutubeDL=FakeYoutubeDL)
        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            YtDlpBackend(
                extra_options={
                    "skip_download": False,
                    "noplaylist": False,
                    "quiet": False,
                    "no_warnings": False,
                    "logger": object(),
                }
            ).inspect("https://youtu.be/BaW_jenozKc")

        self.assertTrue(seen["options"]["skip_download"])
        self.assertTrue(seen["options"]["noplaylist"])
        self.assertTrue(seen["options"]["quiet"])
        self.assertTrue(seen["options"]["no_warnings"])
        self.assertFalse(seen["download"])
        self.assertNotEqual(
            type(seen["options"]["logger"]),
            object,
        )

    def test_backend_allows_safe_operational_extra_options(self):
        seen = {}

        class FakeYoutubeDL:
            def __init__(self, options):
                seen["options"] = options

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, _url, download):
                self.download = download
                return {"id": "BaW_jenozKc", "title": "Test"}

        fake_module = SimpleNamespace(YoutubeDL=FakeYoutubeDL)
        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            YtDlpBackend(
                extra_options={
                    "socket_timeout": 20,
                    "retries": 2,
                }
            ).inspect("https://youtu.be/BaW_jenozKc")

        self.assertEqual(seen["options"]["socket_timeout"], 20)
        self.assertEqual(seen["options"]["retries"], 2)
        self.assertNotIn("cookiefile", seen["options"])
        self.assertNotIn("proxy", seen["options"])

    def test_backend_normalizes_downloader_exception(self):
        class FakeYoutubeDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, _url, download):
                self.assert_false = download
                raise RuntimeError("This video is private")

        fake_module = SimpleNamespace(YoutubeDL=FakeYoutubeDL)
        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            with self.assertRaises(YouTubeServiceError) as caught:
                YtDlpBackend().inspect(
                    "https://www.youtube.com/watch?v=BaW_jenozKc"
                )
        self.assertEqual(caught.exception.code, "private_content")
        self.assertTrue(caught.exception.access_restricted)


class FFmpegCapabilityTests(unittest.TestCase):
    def test_detects_ffmpeg_and_ffprobe(self):
        def fake_which(name):
            return {
                "ffmpeg": "/usr/bin/ffmpeg",
                "ffprobe": "/usr/bin/ffprobe",
            }.get(name)

        with patch("services.youtube_service.shutil.which", side_effect=fake_which):
            capability = detect_ffmpeg()
        self.assertTrue(capability.available)
        self.assertTrue(capability.fully_available)
        self.assertEqual(capability.ffmpeg_path, "/usr/bin/ffmpeg")

    def test_reports_missing_ffprobe_separately(self):
        def fake_which(name):
            return "/usr/bin/ffmpeg" if name == "ffmpeg" else None

        with patch("services.youtube_service.shutil.which", side_effect=fake_which):
            capability = detect_ffmpeg()
        self.assertTrue(capability.available)
        self.assertFalse(capability.fully_available)
        self.assertIsNone(capability.ffprobe_path)


class YouTubeErrorNormalizationTests(unittest.TestCase):
    def test_maps_access_control_failures(self):
        cases = {
            "This video is private": "private_content",
            "This is members-only content": "members_only",
            "This video is DRM protected": "drm_protected",
            "Sign in to confirm your age": "login_required",
            "This video is not available in your country": "geo_restricted",
        }
        for message, code in cases.items():
            with self.subTest(message=message):
                error = normalize_downloader_error(RuntimeError(message))
                self.assertEqual(error.code, code)
                self.assertTrue(error.access_restricted)

    def test_unknown_downloader_error_does_not_expose_raw_message(self):
        raw = (
            "extractor failed for "
            "https://youtube.com/watch?v=BaW_jenozKc&token=secret-value"
        )
        error = normalize_downloader_error(RuntimeError(raw))
        self.assertEqual(error.code, "downloader_error")
        self.assertEqual(
            error.message,
            "YouTube operation failed unexpectedly.",
        )
        self.assertNotIn("secret-value", error.message)
        self.assertNotIn("youtube.com", error.message)

    def test_maps_unavailable_and_network_failures(self):
        unavailable = normalize_downloader_error(RuntimeError("Video unavailable"))
        network = normalize_downloader_error(
            RuntimeError("Connection reset by peer")
        )
        self.assertEqual(unavailable.code, "video_unavailable")
        self.assertFalse(unavailable.access_restricted)
        self.assertEqual(network.code, "network_error")


if __name__ == "__main__":
    unittest.main()
