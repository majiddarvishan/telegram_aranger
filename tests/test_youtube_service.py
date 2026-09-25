import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.youtube_service import (
    YtDlpBackend,
    YouTubeAuthConfig,
    YouTubeProxyConfig,
    YouTubeServiceError,
    detect_ffmpeg,
    detect_local_browser_cookie_source,
    inspect_video,
    materialize_youtube_cookie_file,
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
        self.assertEqual(
            result["url"],
            "https://www.youtube.com/watch?v=BaW_jenozKc",
        )

    def test_canonicalizes_supported_video_url_shapes(self):
        cases = (
            "https://youtu.be/BaW_jenozKc?si=tracking-value",
            "https://youtube.com/shorts/BaW_jenozKc?feature=share",
            "https://youtube.com/live/BaW_jenozKc#fragment",
            "https://www.youtube-nocookie.com/embed/BaW_jenozKc",
        )
        expected = "https://www.youtube.com/watch?v=BaW_jenozKc"

        for url in cases:
            with self.subTest(url=url):
                self.assertEqual(validate_youtube_url(url)["url"], expected)

    def test_rejects_embedded_credentials_and_explicit_ports(self):
        cases = (
            "https://user:secret@youtube.com/watch?v=BaW_jenozKc",
            "https://youtube.com:443/watch?v=BaW_jenozKc",
            "https://youtube.com:8443/watch?v=BaW_jenozKc",
        )
        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(YouTubeServiceError) as caught:
                    validate_youtube_url(url)
                self.assertEqual(caught.exception.code, "invalid_url")

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

    def test_inspection_strips_extra_url_parameters_before_backend(self):
        backend = FakeBackend(self.raw)
        inspect_video(
            "https://youtu.be/BaW_jenozKc?si=tracking-value",
            backend=backend,
        )
        self.assertEqual(
            backend.urls,
            ["https://www.youtube.com/watch?v=BaW_jenozKc"],
        )

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


class YouTubeAuthConfigTests(unittest.TestCase):
    COOKIE_BYTES = (
        b"# Netscape HTTP Cookie File\n"
        b".youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret-value\n"
    )

    def test_validates_youtube_only_netscape_cookie_file(self):
        auth = YouTubeAuthConfig(
            enabled=True,
            cookie_data=self.COOKIE_BYTES,
        )
        normalized = auth.normalized_cookie_bytes()

        self.assertIn(b".youtube.com", normalized)
        self.assertNotIn(b"google.com", normalized)
        summary = auth.as_safe_dict()
        self.assertTrue(summary["enabled"])
        self.assertEqual(summary["format"], "netscape")
        self.assertGreater(summary["size_bytes"], 0)
        self.assertNotIn("secret-value", str(summary))

    def test_rejects_non_netscape_and_non_youtube_cookie_files(self):
        cases = (
            b"not a cookie file",
            (
                b"# Netscape HTTP Cookie File\n"
                b".example.com\tTRUE\t/\tTRUE\t0\tSID\tsecret\n"
            ),
            (
                b"# Netscape HTTP Cookie File\n"
                b".youtube.com\tTRUE\t/\tTRUE\t0\tbroken-row\n"
            ),
        )
        for data in cases:
            with self.subTest(data=data[:40]):
                with self.assertRaises(YouTubeServiceError) as caught:
                    YouTubeAuthConfig(
                        enabled=True,
                        cookie_data=data,
                    ).normalized_cookie_bytes()
                self.assertEqual(caught.exception.code, "youtube_auth_invalid")

    def test_browser_auth_builds_yt_dlp_browser_spec(self):
        auth = YouTubeAuthConfig(
            enabled=True,
            source="browser",
            browser="chrome",
            profile="Profile 2",
        )
        self.assertEqual(
            auth.cookies_from_browser_spec(),
            ("chrome", "Profile 2", None, None),
        )
        self.assertIsNone(auth.normalized_cookie_bytes())
        self.assertEqual(
            auth.as_safe_dict(),
            {
                "enabled": True,
                "source": "browser",
                "browser": "chrome",
                "profile_configured": True,
            },
        )

    def test_auto_browser_detection_uses_standard_profile_roots(self):
        with patch(
            "services.youtube_service.os.path.exists",
            side_effect=lambda path: "google-chrome" in path.lower(),
        ):
            self.assertEqual(
                detect_local_browser_cookie_source(),
                "chrome",
            )

    def test_browser_auth_auto_fails_when_no_local_profile_is_detected(self):
        auth = YouTubeAuthConfig(
            enabled=True,
            source="browser",
            browser="auto",
        )
        with patch(
            "services.youtube_service.detect_local_browser_cookie_source",
            return_value=None,
        ):
            with self.assertRaises(YouTubeServiceError) as caught:
                auth.cookies_from_browser_spec()

        self.assertEqual(
            caught.exception.code,
            "youtube_browser_session_unavailable",
        )

    def test_browser_auth_does_not_materialize_cookie_file(self):
        auth = YouTubeAuthConfig(
            enabled=True,
            source="browser",
            browser="firefox",
        )
        with materialize_youtube_cookie_file(auth) as path:
            self.assertIsNone(path)

    def test_materialized_cookie_file_is_removed_after_operation(self):
        auth = YouTubeAuthConfig(
            enabled=True,
            cookie_data=self.COOKIE_BYTES,
        )
        materialized = None
        with materialize_youtube_cookie_file(auth) as path:
            materialized = path
            self.assertIsNotNone(path)
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(
                open(path, "rb").read(),
                auth.normalized_cookie_bytes(),
            )
        self.assertFalse(os.path.exists(materialized))

    def test_disabled_auth_does_not_materialize_cookie_file(self):
        with materialize_youtube_cookie_file(
            YouTubeAuthConfig(enabled=False)
        ) as path:
            self.assertIsNone(path)


class YouTubeProxyConfigTests(unittest.TestCase):
    def test_disabled_proxy_returns_direct_connection(self):
        proxy = YouTubeProxyConfig(
            enabled=False,
            host="127.0.0.1",
            port=1080,
        )
        self.assertIsNone(proxy.proxy_url())

    def test_builds_socks5_url_without_auth(self):
        proxy = YouTubeProxyConfig(
            enabled=True,
            host="127.0.0.1",
            port=1080,
        )
        self.assertEqual(
            proxy.proxy_url(),
            "socks5://127.0.0.1:1080",
        )

    def test_builds_encoded_authenticated_socks5_url(self):
        proxy = YouTubeProxyConfig(
            enabled=True,
            host="proxy.example",
            port=1081,
            username="user@example.com",
            password="p@ss:/word",
        )
        self.assertEqual(
            proxy.proxy_url(),
            "socks5://user%40example.com:p%40ss%3A%2Fword@proxy.example:1081",
        )

    def test_ipv6_host_is_bracketed(self):
        proxy = YouTubeProxyConfig(
            enabled=True,
            host="2001:db8::1",
            port=1080,
        )
        self.assertEqual(
            proxy.proxy_url(),
            "socks5://[2001:db8::1]:1080",
        )

    def test_rejects_invalid_proxy_inputs(self):
        cases = (
            YouTubeProxyConfig(enabled=True, host="", port=1080),
            YouTubeProxyConfig(
                enabled=True,
                host="socks5://127.0.0.1",
                port=1080,
            ),
            YouTubeProxyConfig(enabled=True, host="proxy host", port=1080),
            YouTubeProxyConfig(enabled=True, host="127.0.0.1", port=0),
            YouTubeProxyConfig(
                enabled=True,
                host="127.0.0.1",
                port=1080,
                password="secret",
            ),
        )
        for proxy in cases:
            with self.subTest(proxy=proxy.as_safe_dict()):
                with self.assertRaises(YouTubeServiceError) as caught:
                    proxy.proxy_url()
                self.assertEqual(caught.exception.code, "proxy_invalid")

    def test_safe_summary_never_contains_proxy_password(self):
        proxy = YouTubeProxyConfig(
            enabled=True,
            host="proxy.example",
            port=1080,
            username="user",
            password="super-secret",
        )
        summary = proxy.as_safe_dict()
        self.assertTrue(summary["password_configured"])
        self.assertNotIn("password", summary)
        self.assertNotIn("super-secret", str(summary))


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

    def test_backend_uses_ephemeral_cookiefile_for_auth(self):
        seen = {}

        class FakeYoutubeDL:
            def __init__(self, options):
                seen["cookiefile"] = options.get("cookiefile")
                seen["cookie_exists_during_init"] = os.path.isfile(
                    seen["cookiefile"]
                )
                seen["cookie_bytes"] = open(
                    seen["cookiefile"], "rb"
                ).read()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, _url, download):
                seen["download"] = download
                return {"id": "BaW_jenozKc", "title": "Test"}

        auth = YouTubeAuthConfig(
            enabled=True,
            cookie_data=YouTubeAuthConfigTests.COOKIE_BYTES,
        )
        fake_module = SimpleNamespace(YoutubeDL=FakeYoutubeDL)
        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            YtDlpBackend(auth=auth).inspect(
                "https://www.youtube.com/watch?v=BaW_jenozKc"
            )

        self.assertTrue(seen["cookie_exists_during_init"])
        self.assertIn(b".youtube.com", seen["cookie_bytes"])
        self.assertFalse(os.path.exists(seen["cookiefile"]))
        self.assertFalse(seen["download"])

    def test_backend_uses_validated_first_class_socks5_proxy(self):
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
        proxy = YouTubeProxyConfig(
            enabled=True,
            host="127.0.0.1",
            port=1080,
            username="proxy-user",
            password="proxy-pass",
        )
        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            YtDlpBackend(proxy=proxy).inspect(
                "https://www.youtube.com/watch?v=BaW_jenozKc"
            )

        self.assertEqual(
            seen["options"]["proxy"],
            "socks5://proxy-user:proxy-pass@127.0.0.1:1080",
        )
        self.assertFalse(seen["download"])

    def test_backend_uses_local_browser_session_cookies(self):
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
        auth = YouTubeAuthConfig(
            enabled=True,
            source="browser",
            browser="firefox",
            profile="default-release",
        )
        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            YtDlpBackend(auth=auth).inspect(
                "https://www.youtube.com/watch?v=BaW_jenozKc"
            )

        self.assertEqual(
            seen["options"]["cookiesfrombrowser"],
            ("firefox", "default-release", None, None),
        )
        self.assertNotIn("cookiefile", seen["options"])
        self.assertFalse(seen["download"])

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
            "This video is not available in your country": "geo_restricted",
        }
        for message, code in cases.items():
            with self.subTest(message=message):
                error = normalize_downloader_error(RuntimeError(message))
                self.assertEqual(error.code, code)
                self.assertTrue(error.access_restricted)

    def test_login_required_is_retryable_with_supported_auth(self):
        error = normalize_downloader_error(
            RuntimeError("Sign in to confirm your age")
        )
        self.assertEqual(error.code, "login_required")
        self.assertFalse(error.access_restricted)
        self.assertIn("Browser session", error.message)
        self.assertNotIn("outside Telegram Harbor V1", error.message)

    def test_maps_youtube_bot_verification_separately_from_content_auth(self):
        messages = (
            "Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication.",
            "Sign in to confirm you’re not a bot. This helps protect our community.",
        )
        for message in messages:
            with self.subTest(message=message):
                error = normalize_downloader_error(RuntimeError(message))
                self.assertEqual(error.code, "bot_verification_required")
                self.assertFalse(error.access_restricted)
                self.assertIn("not a copyright determination", error.message)
                self.assertIn("Browser session", error.message)
                self.assertIn("SOCKS5", error.message)
                self.assertIn("cookies.txt", error.message)
                self.assertIn("cookies.txt", error.message)

    def test_generic_sign_in_to_confirm_is_not_misclassified_as_auth(self):
        error = normalize_downloader_error(
            RuntimeError("Sign in to confirm something unexpected")
        )
        self.assertEqual(error.code, "downloader_error")

    def test_maps_browser_cookie_read_failures(self):
        messages = (
            "ERROR: could not find firefox cookies database in '/home/user/.mozilla'",
            "ERROR: Failed to decrypt with DPAPI",
            "ERROR: failed to load cookies",
        )
        for message in messages:
            with self.subTest(message=message):
                error = normalize_downloader_error(RuntimeError(message))
                self.assertEqual(
                    error.code,
                    "youtube_browser_session_unavailable",
                )
                self.assertFalse(error.access_restricted)
                self.assertNotIn("/home/user", error.message)

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
