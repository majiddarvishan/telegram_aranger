import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.youtube_manual_validate import (
    _result_checks,
    _safe_metadata_summary,
    _subtitle_selection,
    build_parser,
    run,
)
from services.youtube_download import DownloadProgress, DownloadResult
from services.youtube_service import FFmpegCapability, YouTubeServiceError


class ManualValidationHelperTests(unittest.TestCase):
    def test_safe_metadata_summary_excludes_thumbnail_and_raw_urls(self):
        summary = _safe_metadata_summary(
            {
                "video_id": "abc123",
                "title": "Example",
                "channel": "Channel",
                "thumbnail": "https://signed.example/thumb?token=secret",
                "formats": [{"url": "https://signed.example/media?token=secret"}],
                "subtitles": [
                    {
                        "language": "en",
                        "name": "English",
                        "source": "manual",
                        "formats": ["srt", "vtt"],
                        "preferred_format": "srt",
                    }
                ],
            }
        )
        self.assertNotIn("thumbnail", summary)
        self.assertNotIn("url", str(summary).lower())
        self.assertEqual(summary["format_count"], 1)
        self.assertEqual(summary["subtitle_tracks"][0]["source"], "manual")

    def test_subtitle_selection_requires_source_when_language_has_both(self):
        args = SimpleNamespace(
            subtitle_language="en",
            subtitle_source=None,
        )
        metadata = {
            "subtitles": [
                {"language": "en", "source": "manual"},
                {"language": "en", "source": "automatic"},
            ]
        }
        with self.assertRaises(YouTubeServiceError) as caught:
            _subtitle_selection(args, metadata)
        self.assertEqual(caught.exception.code, "subtitle_source_required")

    def test_subtitle_selection_preserves_manual_or_automatic_source(self):
        args = SimpleNamespace(
            subtitle_language="fa",
            subtitle_source="automatic",
        )
        selection = _subtitle_selection(
            args,
            {
                "subtitles": [
                    {"language": "fa", "source": "automatic"},
                ]
            },
        )
        self.assertEqual(selection.language, "fa")
        self.assertEqual(selection.source, "automatic")

    def test_parser_defaults_to_inspect(self):
        args = build_parser().parse_args(
            ["--url", "https://youtu.be/BaW_jenozKc"]
        )
        self.assertEqual(args.mode, "inspect")
        self.assertEqual(args.quality, "best")
        self.assertFalse(args.acknowledge)

    def test_run_inspect_uses_normalized_safe_report(self):
        args = SimpleNamespace(
            url="https://youtu.be/BaW_jenozKc?feature=share",
            mode="inspect",
            quality="best",
            save_directory=None,
            create_directory=False,
            allowed_root=[],
            subtitle_language=None,
            subtitle_source=None,
            acknowledge=False,
            report_file=None,
        )
        metadata = {
            "video_id": "BaW_jenozKc",
            "title": "Test Video",
            "channel": "Test Channel",
            "availability": "public",
            "age_limit": 0,
            "has_drm": False,
            "formats": [{"format_id": "18"}],
            "subtitles": [],
        }
        with (
            patch(
                "scripts.youtube_manual_validate.inspect_video",
                return_value=metadata,
            ),
            patch(
                "scripts.youtube_manual_validate.detect_ffmpeg",
                return_value=FFmpegCapability("/ffmpeg", "/ffprobe"),
            ),
        ):
            report, code = run(args)

        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["video_id"], "BaW_jenozKc")
        self.assertNotIn(args.url, str(report))

    def test_unexpected_runner_error_does_not_expose_raw_message(self):
        args = SimpleNamespace(
            url="https://youtu.be/BaW_jenozKc",
            mode="inspect",
            quality="best",
            save_directory=None,
            create_directory=False,
            allowed_root=[],
            subtitle_language=None,
            subtitle_source=None,
            acknowledge=False,
            report_file=None,
        )
        with (
            patch(
                "scripts.youtube_manual_validate.inspect_video",
                side_effect=RuntimeError(
                    "signed_url=https://example.invalid/media?token=secret-value"
                ),
            ),
            patch(
                "scripts.youtube_manual_validate.detect_ffmpeg",
                return_value=FFmpegCapability("/ffmpeg", "/ffprobe"),
            ),
        ):
            report, code = run(args)

        self.assertEqual(code, 3)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["error"]["code"], "unexpected_error")
        self.assertEqual(
            report["error"]["message"],
            "Unexpected validation failure.",
        )
        self.assertEqual(report["error"]["exception_type"], "RuntimeError")
        self.assertNotIn("secret-value", str(report))
        self.assertNotIn("signed_url", str(report))

    def test_result_checks_require_matched_subtitle_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "My Video.mp4"
            subtitle = root / "My Video.srt"
            media.write_bytes(b"media")
            subtitle.write_text("subtitle", encoding="utf-8")

            result = DownloadResult(
                video_id="BaW_jenozKc",
                title="My Video",
                mode="video_audio",
                quality="best",
                media_path=str(media),
                subtitle_path=str(subtitle),
                subtitle_format="srt",
                subtitle_source="manual",
            )
            checks = _result_checks(
                result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
            )

            self.assertTrue(checks["media_exists"])
            self.assertTrue(checks["subtitle_exists"])
            self.assertTrue(checks["media_within_save_directory"])
            self.assertTrue(checks["subtitle_within_save_directory"])
            self.assertTrue(checks["media_subtitle_basename_match"])
            self.assertTrue(checks["completed_progress_observed"])
            self.assertTrue(checks["all_passed"])

            mismatch = root / "Other.srt"
            subtitle.replace(mismatch)
            mismatched_result = DownloadResult(
                video_id=result.video_id,
                title=result.title,
                mode=result.mode,
                quality=result.quality,
                media_path=result.media_path,
                subtitle_path=str(mismatch),
                subtitle_format="srt",
                subtitle_source="manual",
            )
            checks = _result_checks(
                mismatched_result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
            )
            self.assertFalse(checks["media_subtitle_basename_match"])
            self.assertFalse(checks["all_passed"])

    def test_run_download_uses_service_contract_and_reports_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = SimpleNamespace(
                url="https://youtu.be/BaW_jenozKc",
                mode="video_audio",
                quality="max_720p",
                save_directory=tmp,
                create_directory=False,
                allowed_root=[],
                subtitle_language=None,
                subtitle_source=None,
                acknowledge=True,
                report_file=None,
            )
            metadata = {
                "video_id": "BaW_jenozKc",
                "title": "Test Video",
                "channel": "Test Channel",
                "availability": "public",
                "age_limit": 0,
                "has_drm": False,
                "formats": [{"format_id": "18"}],
                "subtitles": [],
            }
            media_path = Path(tmp) / "Test Video.mp4"
            media_path.write_bytes(b"media")
            result = DownloadResult(
                video_id="BaW_jenozKc",
                title="Test Video",
                mode="video_audio",
                quality="max_720p",
                media_path=str(media_path),
                subtitle_path=None,
                subtitle_format=None,
                subtitle_source=None,
            )
            def fake_download(*call_args, **call_kwargs):
                callback = call_kwargs.get("progress_callback")
                if callback is not None:
                    callback(
                        DownloadProgress(
                            phase="completed",
                            status="finished",
                            percent=100.0,
                            final_output_path=str(media_path),
                        )
                    )
                return result

            with (
                patch(
                    "scripts.youtube_manual_validate.inspect_video",
                    return_value=metadata,
                ),
                patch(
                    "scripts.youtube_manual_validate.detect_ffmpeg",
                    return_value=FFmpegCapability("/ffmpeg", "/ffprobe"),
                ),
                patch(
                    "scripts.youtube_manual_validate.download_video",
                    side_effect=fake_download,
                ) as download_mock,
            ):
                report, code = run(args)

            self.assertEqual(code, 0)
            self.assertEqual(report["result"]["media_path"], result.media_path)
            self.assertTrue(report["checks"]["completed_progress_observed"])
            self.assertTrue(report["checks"]["all_passed"])
            request = download_mock.call_args.args[0]
            self.assertTrue(request.acknowledged)
            self.assertEqual(request.mode, "video_audio")
            self.assertEqual(request.quality, "max_720p")


if __name__ == "__main__":
    unittest.main()
