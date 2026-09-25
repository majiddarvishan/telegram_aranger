import unittest
from pathlib import Path

from services.youtube_download import DownloadProgress
from ui.youtube import (
    _format_bytes,
    _format_duration,
    _progress_text,
    _quality_options,
    _subtitle_label,
)


class YouTubeUiFormattingTests(unittest.TestCase):
    def test_formats_duration_and_sizes(self):
        self.assertEqual(_format_duration(65), "1:05")
        self.assertEqual(_format_duration(3661), "1:01:01")
        self.assertEqual(_format_duration(None), "Unknown")
        self.assertEqual(_format_bytes(1024), "1.0 KB")
        self.assertEqual(_format_bytes(None), "Unknown")

    def test_quality_options_only_expose_available_presets(self):
        metadata = {
            "quality_presets": [
                {
                    "key": "best",
                    "label": "Best available",
                    "available": True,
                },
                {
                    "key": "max_1080p",
                    "label": "Up to 1080p",
                    "available": False,
                },
                {
                    "key": "max_720p",
                    "label": "Up to 720p",
                    "available": True,
                },
            ]
        }
        self.assertEqual(
            _quality_options(metadata),
            [
                ("best", "Best available"),
                ("max_720p", "Up to 720p"),
            ],
        )

    def test_subtitle_labels_distinguish_manual_and_auto_generated(self):
        manual = _subtitle_label(
            {
                "language": "en",
                "name": "English",
                "source": "manual",
                "preferred_format": "srt",
            }
        )
        automatic = _subtitle_label(
            {
                "language": "fa",
                "name": "Persian",
                "source": "automatic",
                "preferred_format": "vtt",
            }
        )
        self.assertIn("Manual", manual)
        self.assertIn("SRT", manual)
        self.assertIn("Auto-generated", automatic)
        self.assertIn("VTT", automatic)

    def test_progress_text_exposes_estimated_total_speed_eta_and_phase(self):
        event = DownloadProgress(
            phase="downloading",
            status="downloading",
            percent=25.0,
            downloaded_bytes=25 * 1024,
            total_bytes=100 * 1024,
            total_is_estimate=True,
            speed_bytes_per_second=10 * 1024,
            eta_seconds=8,
        )
        text = _progress_text(event)
        self.assertIn("Downloading", text)
        self.assertIn("~100.0 KB", text)
        self.assertIn("10.0 KB/s", text)
        self.assertIn("ETA 8s", text)


class YouTubeUiArchitectureTests(unittest.TestCase):
    def test_app_routes_to_independent_youtube_workspace(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        sidebar_source = Path("ui/sidebar.py").read_text(encoding="utf-8")
        self.assertIn("workspace = render_sidebar(settings)", app_source)
        self.assertIn("render_youtube(settings)", app_source)
        self.assertIn(
            '("Telegram Messages", "YouTube Download")',
            sidebar_source,
        )

    def test_ui_keeps_downloader_details_behind_services(self):
        source = Path("ui/youtube.py").read_text(encoding="utf-8")
        self.assertNotIn("import yt_dlp", source)
        self.assertIn("inspect_video", source)
        self.assertIn("download_video", source)

    def test_ui_uses_responsive_workspace_keys(self):
        source = Path("ui/youtube.py").read_text(encoding="utf-8")
        self.assertIn('key="youtube-thumbnail"', source)
        self.assertIn('key="youtube-metadata-metrics"', source)
        self.assertIn('key="youtube-output-controls"', source)
        self.assertIn('key="youtube-save-controls"', source)
        self.assertIn("use_container_width=True", source)

    def test_notice_is_rendered_before_acknowledgement_control(self):
        source = Path("ui/youtube.py").read_text(encoding="utf-8")
        notice_position = source.index(
            "base_policy = _render_restriction_state(metadata)"
        )
        acknowledgement_position = source.index(
            '"I acknowledge the rights/service notice and want to continue."'
        )
        self.assertLess(notice_position, acknowledgement_position)
        self.assertIn("if base_policy.blocked:", source)
        self.assertIn("acknowledged = False", source)

    def test_ui_does_not_render_raw_unexpected_exception_text(self):
        source = Path("ui/youtube.py").read_text(encoding="utf-8")
        self.assertNotIn('st.error(f"YouTube download failed: {exc}")', source)
        self.assertNotIn('"message": str(exc)', source)
        self.assertIn("YouTube download failed unexpectedly.", source)
        self.assertIn("YouTube inspection failed unexpectedly.", source)

    def test_ui_contains_v1_safety_and_progress_contract(self):
        source = Path("ui/youtube.py").read_text(encoding="utf-8")
        self.assertIn("Save directory", source)
        self.assertIn("server host", source)
        self.assertIn("rights/service notice", source)
        self.assertIn("Subtitle / caption tracks", source)
        self.assertIn("st.progress", source)
        self.assertIn("FFmpeg and FFprobe", source)


if __name__ == "__main__":
    unittest.main()
