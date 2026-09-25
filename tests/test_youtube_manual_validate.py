import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.youtube_manual_validate import (
    _binary_runtime_available,
    _environment_summary,
    _request_summary,
    _result_checks,
    _safe_metadata_summary,
    _subtitle_selection,
    build_parser,
    run,
)
from services.youtube_download import DownloadProgress, DownloadResult
from services.youtube_service import FFmpegCapability, YouTubeServiceError


class ManualValidationHelperTests(unittest.TestCase):
    def test_binary_runtime_available_requires_successful_execution(self):
        with patch(
            "scripts.youtube_manual_validate.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ) as run_mock:
            self.assertTrue(_binary_runtime_available("/ffmpeg"))
        run_mock.assert_called_once()

        with patch(
            "scripts.youtube_manual_validate.subprocess.run",
            return_value=SimpleNamespace(returncode=1),
        ):
            self.assertFalse(_binary_runtime_available("/ffmpeg"))

        with patch(
            "scripts.youtube_manual_validate.subprocess.run",
            side_effect=OSError("broken"),
        ):
            self.assertFalse(_binary_runtime_available("/ffmpeg"))

        self.assertFalse(_binary_runtime_available(None))

    def test_request_summary_records_safe_reproducible_inputs(self):
        args = SimpleNamespace(
            mode="video_audio",
            quality="max_720p",
            save_directory="/srv/youtube/output",
            create_directory=True,
            allowed_root=["/srv/youtube"],
            subtitle_language="en",
            subtitle_source="manual",
            acknowledge=True,
        )
        summary = _request_summary(args)

        self.assertEqual(summary["mode"], "video_audio")
        self.assertEqual(summary["quality"], "max_720p")
        self.assertEqual(summary["save_directory"], "/srv/youtube/output")
        self.assertEqual(summary["allowed_roots"], ["/srv/youtube"])
        self.assertEqual(summary["subtitle_language"], "en")
        self.assertEqual(summary["subtitle_source"], "manual")
        self.assertTrue(summary["acknowledged"])
        self.assertNotIn("url", summary)

    def test_environment_summary_records_build_identity_without_hostname(self):
        with patch.dict(
            "os.environ",
            {"TELEGRAM_HARBOR_BUILD_SHA": "abc123def456"},
            clear=False,
        ):
            summary = _environment_summary()

        self.assertEqual(summary["commit_sha"], "abc123def456")
        self.assertIn("python_version", summary)
        self.assertIn("platform", summary)
        self.assertIn("platform_release", summary)
        self.assertIn("machine", summary)
        self.assertIn("docker", summary)
        self.assertIn("app_version", summary)
        self.assertNotIn("hostname", summary)
        self.assertNotIn("username", summary)
        self.assertNotIn("environment", summary)

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

        preflight = build_parser().parse_args(
            ["--mode", "preflight", "--save-directory", "/tmp"]
        )
        self.assertEqual(preflight.mode, "preflight")
        self.assertIsNone(preflight.url)

        collision = build_parser().parse_args(
            [
                "--url",
                "https://youtu.be/BaW_jenozKc",
                "--mode",
                "video_audio",
                "--expect-collision",
            ]
        )
        self.assertTrue(collision.expect_collision)

    def test_missing_url_returns_structured_failure_report(self):
        args = SimpleNamespace(
            url=None,
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
        with patch(
            "scripts.youtube_manual_validate.detect_ffmpeg",
            return_value=FFmpegCapability("/ffmpeg", "/ffprobe"),
        ):
            report, code = run(args)

        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["error"]["code"], "invalid_url")
        self.assertIn("finished_at", report)

    def test_download_without_acknowledgement_returns_structured_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = SimpleNamespace(
                url="https://youtu.be/BaW_jenozKc",
                mode="video_audio",
                quality="best",
                save_directory=tmp,
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
                "availability": "public",
                "age_limit": 0,
                "is_live": False,
                "live_status": "not_live",
                "has_drm": False,
                "formats": [
                    {"format_id": "18", "has_video": True, "has_audio": True}
                ],
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
                patch(
                    "scripts.youtube_manual_validate.download_video",
                    side_effect=YouTubeServiceError(
                        "acknowledgement_required",
                        "You must acknowledge the rights/service notice before downloading.",
                    ),
                ),
            ):
                report, code = run(args)

        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(
            report["error"]["code"],
            "acknowledgement_required",
        )
        self.assertFalse(report["request"]["acknowledged"])

    def test_invalid_url_returns_structured_failure_report(self):
        args = SimpleNamespace(
            url="https://example.com/not-youtube",
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
        with patch(
            "scripts.youtube_manual_validate.detect_ffmpeg",
            return_value=FFmpegCapability("/ffmpeg", "/ffprobe"),
        ):
            report, code = run(args)

        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["error"]["code"], "unsupported_url")
        self.assertIsNone(report["video_id"])
        self.assertIn("finished_at", report)

    def test_preflight_validates_path_and_ffmpeg_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = SimpleNamespace(
                url=None,
                mode="preflight",
                quality="best",
                save_directory=tmp,
                create_directory=False,
                allowed_root=[],
                subtitle_language=None,
                subtitle_source=None,
                acknowledge=False,
                report_file=None,
            )
            with (
                patch(
                    "scripts.youtube_manual_validate.detect_ffmpeg",
                    return_value=FFmpegCapability("/ffmpeg", "/ffprobe"),
                ),
                patch(
                    "scripts.youtube_manual_validate.inspect_video"
                ) as inspect_mock,
                patch(
                    "scripts.youtube_manual_validate.download_video"
                ) as download_mock,
                patch(
                    "scripts.youtube_manual_validate._binary_runtime_available",
                    return_value=True,
                ),
            ):
                report, code = run(args)

        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["preflight"]["save_directory_valid"])
        self.assertTrue(report["preflight"]["ffmpeg_fully_available"])
        self.assertTrue(report["preflight"]["ffmpeg_runtime_ok"])
        self.assertTrue(report["preflight"]["ffprobe_runtime_ok"])
        self.assertTrue(report["preflight"]["ffmpeg_runtime_ready"])
        self.assertIsNone(report["video_id"])
        inspect_mock.assert_not_called()
        download_mock.assert_not_called()

    def test_preflight_fails_when_ffmpeg_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = SimpleNamespace(
                url=None,
                mode="preflight",
                quality="best",
                save_directory=tmp,
                create_directory=False,
                allowed_root=[],
                subtitle_language=None,
                subtitle_source=None,
                acknowledge=False,
                report_file=None,
            )
            with (
                patch(
                    "scripts.youtube_manual_validate.detect_ffmpeg",
                    return_value=FFmpegCapability("/ffmpeg", None),
                ),
                patch(
                    "scripts.youtube_manual_validate._binary_runtime_available",
                    side_effect=lambda path: bool(path),
                ),
            ):
                report, code = run(args)

        self.assertEqual(code, 4)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["error"]["code"], "ffmpeg_unavailable")
        self.assertFalse(report["preflight"]["ffmpeg_fully_available"])

    def test_preflight_fails_when_ffmpeg_binary_cannot_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = SimpleNamespace(
                url=None,
                mode="preflight",
                quality="best",
                save_directory=tmp,
                create_directory=False,
                allowed_root=[],
                subtitle_language=None,
                subtitle_source=None,
                acknowledge=False,
                report_file=None,
            )
            with (
                patch(
                    "scripts.youtube_manual_validate.detect_ffmpeg",
                    return_value=FFmpegCapability("/ffmpeg", "/ffprobe"),
                ),
                patch(
                    "scripts.youtube_manual_validate._binary_runtime_available",
                    side_effect=[False, True],
                ),
            ):
                report, code = run(args)

        self.assertEqual(code, 4)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(
            report["error"]["code"],
            "ffmpeg_runtime_unavailable",
        )
        self.assertFalse(report["preflight"]["ffmpeg_runtime_ready"])

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
        self.assertIn("environment", report)
        self.assertIn("commit_sha", report["environment"])
        self.assertIn("request", report)
        self.assertEqual(report["request"]["mode"], "inspect")
        self.assertNotIn("url", report["request"])
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
            self.assertGreater(checks["media_size_bytes"], 0)
            self.assertTrue(checks["media_nonempty"])
            self.assertTrue(checks["subtitle_exists"])
            self.assertGreater(checks["subtitle_size_bytes"], 0)
            self.assertTrue(checks["subtitle_nonempty"])
            self.assertTrue(checks["media_within_save_directory"])
            self.assertTrue(checks["subtitle_within_save_directory"])
            self.assertTrue(checks["media_subtitle_basename_match"])
            self.assertTrue(checks["completed_progress_observed"])
            self.assertTrue(checks["title_based_output_name"])
            self.assertTrue(checks["media_extension_matches_mode"])
            self.assertTrue(checks["subtitle_extension_matches_report"])
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

    def test_result_checks_reject_empty_media_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "My Video.mp4"
            media.write_bytes(b"")
            result = DownloadResult(
                video_id="BaW_jenozKc",
                title="My Video",
                mode="video_audio",
                quality="best",
                media_path=str(media),
                subtitle_path=None,
                subtitle_format=None,
                subtitle_source=None,
            )

            checks = _result_checks(
                result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
            )

            self.assertTrue(checks["media_exists"])
            self.assertEqual(checks["media_size_bytes"], 0)
            self.assertFalse(checks["media_nonempty"])
            self.assertFalse(checks["all_passed"])

    def test_result_checks_reject_empty_requested_subtitle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "My Video.mp4"
            subtitle = root / "My Video.srt"
            media.write_bytes(b"media")
            subtitle.write_bytes(b"")
            result = DownloadResult(
                video_id="BaW_jenozKc",
                title="My Video",
                mode="video_audio",
                quality="best",
                media_path=str(media),
                subtitle_path=str(subtitle),
                subtitle_format="srt",
                subtitle_source="manual",
                subtitle_language="en",
            )

            checks = _result_checks(
                result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
                subtitle_expected=True,
                expected_subtitle_source="manual",
                expected_subtitle_language="en",
            )

            self.assertTrue(checks["subtitle_exists"])
            self.assertEqual(checks["subtitle_size_bytes"], 0)
            self.assertFalse(checks["subtitle_nonempty"])
            self.assertFalse(checks["all_passed"])

    def test_result_checks_fail_when_requested_subtitle_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "My Video.mp4"
            media.write_bytes(b"media")
            result = DownloadResult(
                video_id="BaW_jenozKc",
                title="My Video",
                mode="video_audio",
                quality="best",
                media_path=str(media),
                subtitle_path=None,
                subtitle_format=None,
                subtitle_source=None,
            )

            checks = _result_checks(
                result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
                subtitle_expected=True,
                expected_subtitle_source="manual",
            )

            self.assertFalse(checks["subtitle_exists"])
            self.assertFalse(checks["subtitle_presence_matches_request"])
            self.assertFalse(checks["subtitle_source_matches_request"])
            self.assertFalse(checks["all_passed"])

    def test_result_checks_fail_when_subtitle_source_does_not_match_request(self):
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
                subtitle_source="automatic",
                subtitle_language="fa",
            )

            checks = _result_checks(
                result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
                subtitle_expected=True,
                expected_subtitle_source="manual",
                expected_subtitle_language="en",
            )

            self.assertTrue(checks["subtitle_presence_matches_request"])
            self.assertFalse(checks["subtitle_source_matches_request"])
            self.assertFalse(checks["subtitle_language_matches_request"])
            self.assertFalse(checks["all_passed"])

    def test_collision_expectation_requires_numeric_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plain = root / "Human Readable Title.mp4"
            plain.write_bytes(b"media")
            plain_result = DownloadResult(
                video_id="BaW_jenozKc",
                title="Human Readable Title",
                mode="video_audio",
                quality="best",
                media_path=str(plain),
                subtitle_path=None,
                subtitle_format=None,
                subtitle_source=None,
            )
            checks = _result_checks(
                plain_result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
                expect_collision=True,
            )
            self.assertFalse(checks["collision_expectation_met"])
            self.assertFalse(checks["all_passed"])

            collided = root / "Human Readable Title (2).mp4"
            plain.replace(collided)
            collided_result = DownloadResult(
                video_id=plain_result.video_id,
                title=plain_result.title,
                mode=plain_result.mode,
                quality=plain_result.quality,
                media_path=str(collided),
                subtitle_path=None,
                subtitle_format=None,
                subtitle_source=None,
            )
            checks = _result_checks(
                collided_result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
                expect_collision=True,
            )
            self.assertEqual(checks["collision_number"], 2)
            self.assertTrue(checks["collision_expectation_met"])
            self.assertTrue(checks["all_passed"])

    def test_result_checks_accept_matching_subtitle_language(self):
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
                subtitle_language="en",
            )

            checks = _result_checks(
                result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
                subtitle_expected=True,
                expected_subtitle_source="manual",
                expected_subtitle_language="en",
            )

            self.assertTrue(checks["subtitle_language_matches_request"])
            self.assertTrue(checks["all_passed"])

    def test_result_checks_reject_non_title_based_or_wrong_extension_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "BaW_jenozKc.webm"
            media.write_bytes(b"media")
            result = DownloadResult(
                video_id="BaW_jenozKc",
                title="Human Readable Title",
                mode="video_audio",
                quality="best",
                media_path=str(media),
                subtitle_path=None,
                subtitle_format=None,
                subtitle_source=None,
            )

            checks = _result_checks(
                result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
            )

            self.assertFalse(checks["title_based_output_name"])
            self.assertFalse(checks["media_extension_matches_mode"])
            self.assertFalse(checks["all_passed"])

    def test_result_checks_accept_collision_suffix_for_title_based_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "Human Readable Title (2).mp4"
            media.write_bytes(b"media")
            result = DownloadResult(
                video_id="BaW_jenozKc",
                title="Human Readable Title",
                mode="video_audio",
                quality="best",
                media_path=str(media),
                subtitle_path=None,
                subtitle_format=None,
                subtitle_source=None,
            )

            checks = _result_checks(
                result,
                tmp,
                [{"phase": "completed", "status": "finished"}],
            )

            self.assertTrue(checks["title_based_output_name"])
            self.assertTrue(checks["media_extension_matches_mode"])
            self.assertTrue(checks["all_passed"])

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
