import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.youtube_download import (
    DownloadRequest,
    SubtitleSelection,
    build_download_options,
    build_subtitle_plan,
    download_video,
    format_selector,
    normalize_download_error,
    progress_hook,
    resolve_media_source,
    resolve_subtitle_source,
    try_convert_subtitle_to_srt,
)
from services.youtube_service import FFmpegCapability, YouTubeServiceError


def metadata(**overrides):
    value = {
        "video_id": "BaW_jenozKc",
        "title": "My Video",
        "availability": "public",
        "age_limit": 0,
        "is_live": False,
        "live_status": "not_live",
        "has_drm": False,
        "formats": [
            {"format_id": "22", "has_video": True, "has_audio": True}
        ],
        "subtitles": [
            {
                "language": "en",
                "name": "English",
                "source": "manual",
                "formats": ["srt", "vtt"],
                "preferred_format": "srt",
            },
            {
                "language": "fa",
                "name": "Persian",
                "source": "automatic",
                "formats": ["vtt"],
                "preferred_format": "vtt",
            },
            {
                "language": "de",
                "name": "German",
                "source": "manual",
                "formats": ["ttml"],
                "preferred_format": "ttml",
            },
        ],
    }
    value.update(overrides)
    return value


class FakeDownloadBackend:
    def __init__(
        self,
        *,
        fail=None,
        empty_media=False,
        empty_subtitle=False,
    ):
        self.fail = fail
        self.empty_media = empty_media
        self.empty_subtitle = empty_subtitle
        self.options = None
        self.url = None

    def download(self, url, options):
        self.url = url
        self.options = dict(options)
        if self.fail:
            raise self.fail

        temp = Path(options["paths"]["home"])
        template = Path(options["outtmpl"]["default"]).name
        basename = template.removesuffix(".%(ext)s")
        media_ext = options["final_ext"]
        media = temp / f"{basename}.{media_ext}"
        media.write_bytes(b"" if self.empty_media else b"media")

        requested_subtitles = {}
        langs = options.get("subtitleslangs") or []
        if langs:
            lang = langs[0]
            sub_ext = options["subtitlesformat"].split("/")[0]
            subtitle = temp / f"{basename}.{lang}.{sub_ext}"
            subtitle.write_text(
                "" if self.empty_subtitle else "subtitle",
                encoding="utf-8",
            )
            requested_subtitles[lang] = {
                "filepath": str(subtitle),
                "ext": sub_ext,
            }

        for hook in options["progress_hooks"]:
            hook(
                {
                    "status": "downloading",
                    "downloaded_bytes": 50,
                    "total_bytes": 100,
                    "speed": 25,
                    "eta": 2,
                }
            )
            hook(
                {
                    "status": "finished",
                    "downloaded_bytes": 100,
                    "total_bytes": 100,
                }
            )
        for hook in options["postprocessor_hooks"]:
            hook({"status": "started", "postprocessor": "FakePP"})
            hook({"status": "finished", "postprocessor": "FakePP"})

        return {
            "filepath": str(media),
            "requested_subtitles": requested_subtitles,
        }


FFMPEG = FFmpegCapability(
    ffmpeg_path="/fake/ffmpeg",
    ffprobe_path="/fake/ffprobe",
)


class DownloadOptionTests(unittest.TestCase):
    def test_quality_selectors(self):
        self.assertEqual(format_selector("video_audio", "best"), "bv*+ba/b")
        self.assertEqual(
            format_selector("video_audio", "max_720p"),
            "bv*[height<=720]+ba/b[height<=720]",
        )
        self.assertEqual(format_selector("audio_only", "best"), "ba/b")

    def test_video_options_remux_to_mp4_without_exposing_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = build_download_options(
                temp_directory=Path(tmp),
                basename="My Video",
                mode="video_audio",
                quality="max_1080p",
                subtitle_plan=None,
                progress_callback=None,
            )

        self.assertEqual(options["merge_output_format"], "mp4")
        self.assertEqual(options["final_ext"], "mp4")
        self.assertFalse(options["overwrites"])
        self.assertTrue(options["quiet"])
        self.assertTrue(options["noplaylist"])
        self.assertEqual(
            options["postprocessors"][0]["key"],
            "FFmpegVideoRemuxer",
        )
        self.assertNotIn("proxy", options)
        self.assertNotIn("cookiefile", options)

    def test_audio_options_extract_mp3(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = build_download_options(
                temp_directory=Path(tmp),
                basename="Track",
                mode="audio_only",
                quality="best",
                subtitle_plan=None,
                progress_callback=None,
            )

        pp = options["postprocessors"][0]
        self.assertEqual(pp["key"], "FFmpegExtractAudio")
        self.assertEqual(pp["preferredcodec"], "mp3")
        self.assertEqual(options["final_ext"], "mp3")


class SubtitlePlanTests(unittest.TestCase):
    def test_manual_srt_is_used_directly(self):
        plan = build_subtitle_plan(
            metadata(),
            SubtitleSelection(language="en", source="manual"),
        )
        self.assertEqual(plan["requested_format"], "srt")
        self.assertTrue(plan["prefer_srt"])

    def test_auto_vtt_is_selected_for_later_srt_conversion(self):
        plan = build_subtitle_plan(
            metadata(),
            SubtitleSelection(language="fa", source="automatic"),
        )
        self.assertEqual(plan["requested_format"], "vtt")
        self.assertTrue(plan["prefer_srt"])

    def test_original_format_is_fallback_when_srt_vtt_are_absent(self):
        plan = build_subtitle_plan(
            metadata(),
            SubtitleSelection(language="de", source="manual"),
        )
        self.assertEqual(plan["requested_format"], "ttml")
        self.assertFalse(plan["prefer_srt"])

    def test_missing_track_is_rejected(self):
        with self.assertRaises(YouTubeServiceError) as caught:
            build_subtitle_plan(
                metadata(),
                SubtitleSelection(language="fr", source="manual"),
            )
        self.assertEqual(caught.exception.code, "subtitle_unavailable")


class DownloadExecutionTests(unittest.TestCase):
    def test_video_download_reports_progress_and_final_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = FakeDownloadBackend()
            events = []
            result = download_video(
                DownloadRequest(
                    url="https://www.youtube.com/watch?v=BaW_jenozKc",
                    save_directory=tmp,
                    acknowledged=True,
                ),
                metadata(),
                backend=backend,
                ffmpeg=FFMPEG,
                progress_callback=events.append,
            )

            self.assertEqual(Path(result.media_path).name, "My Video.mp4")
            self.assertTrue(Path(result.media_path).is_file())
            self.assertEqual(result.subtitle_path, None)
            self.assertTrue(any(event.percent == 50.0 for event in events))
            self.assertEqual(events[-1].phase, "completed")
            self.assertEqual(events[-1].final_output_path, result.media_path)

    def test_download_backend_receives_canonical_video_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = FakeDownloadBackend()
            download_video(
                DownloadRequest(
                    url="https://youtu.be/BaW_jenozKc?si=tracking-value",
                    save_directory=tmp,
                    acknowledged=True,
                ),
                metadata(),
                backend=backend,
                ffmpeg=FFMPEG,
            )

            self.assertEqual(
                backend.url,
                "https://www.youtube.com/watch?v=BaW_jenozKc",
            )

    def test_audio_only_output_is_mp3(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = download_video(
                DownloadRequest(
                    url="https://youtu.be/BaW_jenozKc",
                    save_directory=tmp,
                    mode="audio_only",
                    acknowledged=True,
                ),
                metadata(),
                backend=FakeDownloadBackend(),
                ffmpeg=FFMPEG,
            )
            self.assertEqual(Path(result.media_path).suffix, ".mp3")

    def test_manual_subtitle_shares_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = download_video(
                DownloadRequest(
                    url="https://youtu.be/BaW_jenozKc",
                    save_directory=tmp,
                    subtitle=SubtitleSelection("en", "manual"),
                    acknowledged=True,
                ),
                metadata(),
                backend=FakeDownloadBackend(),
                ffmpeg=FFMPEG,
            )

            self.assertEqual(Path(result.media_path).stem, "My Video")
            self.assertEqual(Path(result.subtitle_path).stem, "My Video")
            self.assertEqual(result.subtitle_format, "srt")
            self.assertEqual(result.subtitle_source, "manual")
            self.assertEqual(result.subtitle_language, "en")

    def test_vtt_conversion_success_reports_srt(self):
        with tempfile.TemporaryDirectory() as tmp:
            def converted(source, target, ffmpeg_path, progress_callback=None):
                target.write_text("converted", encoding="utf-8")
                return target, "srt"

            with patch(
                "services.youtube_download.try_convert_subtitle_to_srt",
                side_effect=converted,
            ):
                result = download_video(
                    DownloadRequest(
                        url="https://youtu.be/BaW_jenozKc",
                        save_directory=tmp,
                        subtitle=SubtitleSelection("fa", "automatic"),
                        acknowledged=True,
                    ),
                    metadata(),
                    backend=FakeDownloadBackend(),
                    ffmpeg=FFMPEG,
                )

            self.assertEqual(result.subtitle_format, "srt")
            self.assertEqual(Path(result.subtitle_path).suffix, ".srt")
            self.assertEqual(result.subtitle_source, "automatic")
            self.assertEqual(result.subtitle_language, "fa")

    def test_vtt_conversion_failure_keeps_actual_vtt_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fallback(source, target, ffmpeg_path, progress_callback=None):
                return source, "vtt"

            with patch(
                "services.youtube_download.try_convert_subtitle_to_srt",
                side_effect=fallback,
            ):
                result = download_video(
                    DownloadRequest(
                        url="https://youtu.be/BaW_jenozKc",
                        save_directory=tmp,
                        subtitle=SubtitleSelection("fa", "automatic"),
                        acknowledged=True,
                    ),
                    metadata(),
                    backend=FakeDownloadBackend(),
                    ffmpeg=FFMPEG,
                )

            self.assertEqual(result.subtitle_format, "vtt")
            self.assertEqual(Path(result.subtitle_path).suffix, ".vtt")

    def test_collision_suffix_applies_to_media_and_subtitle_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "My Video.mp4").write_bytes(b"existing")
            result = download_video(
                DownloadRequest(
                    url="https://youtu.be/BaW_jenozKc",
                    save_directory=tmp,
                    subtitle=SubtitleSelection("en", "manual"),
                    acknowledged=True,
                ),
                metadata(),
                backend=FakeDownloadBackend(),
                ffmpeg=FFMPEG,
            )

            self.assertEqual(Path(result.media_path).name, "My Video (2).mp4")
            self.assertEqual(Path(result.subtitle_path).name, "My Video (2).srt")

    def test_stale_metadata_for_different_video_is_rejected_before_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = FakeDownloadBackend()
            with self.assertRaises(YouTubeServiceError) as caught:
                download_video(
                    DownloadRequest(
                        url="https://youtu.be/BaW_jenozKc",
                        save_directory=tmp,
                        acknowledged=True,
                    ),
                    metadata(video_id="Different123"),
                    backend=backend,
                    ffmpeg=FFMPEG,
                )

            self.assertEqual(
                caught.exception.code,
                "metadata_video_mismatch",
            )
            self.assertIsNone(backend.options)

    def test_backend_output_for_different_video_is_rejected_and_cleaned(self):
        class MismatchedBackend(FakeDownloadBackend):
            def download(self, url, options):
                info = dict(super().download(url, options))
                info["id"] = "Different123"
                return info

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(YouTubeServiceError) as caught:
                download_video(
                    DownloadRequest(
                        url="https://youtu.be/BaW_jenozKc",
                        save_directory=tmp,
                        acknowledged=True,
                    ),
                    metadata(),
                    backend=MismatchedBackend(),
                    ffmpeg=FFMPEG,
                )

            self.assertEqual(
                caught.exception.code,
                "download_video_mismatch",
            )
            self.assertEqual(list(root.iterdir()), [])

    def test_acknowledgement_is_enforced_before_backend_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = FakeDownloadBackend()
            with self.assertRaises(YouTubeServiceError) as caught:
                download_video(
                    DownloadRequest(
                        url="https://youtu.be/BaW_jenozKc",
                        save_directory=tmp,
                        acknowledged=False,
                    ),
                    metadata(),
                    backend=backend,
                    ffmpeg=FFMPEG,
                )

            self.assertEqual(caught.exception.code, "acknowledgement_required")
            self.assertIsNone(backend.options)

    def test_missing_ffmpeg_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(YouTubeServiceError) as caught:
                download_video(
                    DownloadRequest(
                        url="https://youtu.be/BaW_jenozKc",
                        save_directory=tmp,
                        acknowledged=True,
                    ),
                    metadata(),
                    backend=FakeDownloadBackend(),
                    ffmpeg=FFmpegCapability(None, None),
                )
            self.assertEqual(caught.exception.code, "ffmpeg_unavailable")

    def test_empty_media_output_is_rejected_and_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(YouTubeServiceError) as caught:
                download_video(
                    DownloadRequest(
                        url="https://youtu.be/BaW_jenozKc",
                        save_directory=tmp,
                        acknowledged=True,
                    ),
                    metadata(),
                    backend=FakeDownloadBackend(empty_media=True),
                    ffmpeg=FFMPEG,
                )

            self.assertEqual(caught.exception.code, "output_empty")
            self.assertEqual(list(root.iterdir()), [])

    def test_empty_subtitle_output_is_rejected_and_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(YouTubeServiceError) as caught:
                download_video(
                    DownloadRequest(
                        url="https://youtu.be/BaW_jenozKc",
                        save_directory=tmp,
                        subtitle=SubtitleSelection("en", "manual"),
                        acknowledged=True,
                    ),
                    metadata(),
                    backend=FakeDownloadBackend(empty_subtitle=True),
                    ffmpeg=FFMPEG,
                )

            self.assertEqual(
                caught.exception.code,
                "subtitle_output_empty",
            )
            self.assertEqual(list(root.iterdir()), [])

    def test_failed_download_leaves_no_final_or_temp_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(YouTubeServiceError):
                download_video(
                    DownloadRequest(
                        url="https://youtu.be/BaW_jenozKc",
                        save_directory=tmp,
                        acknowledged=True,
                    ),
                    metadata(),
                    backend=FakeDownloadBackend(
                        fail=YouTubeServiceError(
                            "network_error",
                            "Network failed.",
                        )
                    ),
                    ffmpeg=FFMPEG,
                )

            self.assertEqual(list(root.iterdir()), [])


class TempOutputContainmentTests(unittest.TestCase):
    def test_media_filepath_outside_job_temp_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = root / "job"
            job.mkdir()
            outside = root / "outside.mp4"
            outside.write_bytes(b"outside")

            with self.assertRaises(YouTubeServiceError) as caught:
                resolve_media_source(
                    {"filepath": str(outside)},
                    job,
                    "My Video",
                    "mp4",
                )

            self.assertEqual(caught.exception.code, "output_missing")
            self.assertTrue(outside.exists())

    def test_subtitle_filepath_outside_job_temp_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = root / "job"
            job.mkdir()
            outside = root / "outside.srt"
            outside.write_text("outside", encoding="utf-8")

            with self.assertRaises(YouTubeServiceError) as caught:
                resolve_subtitle_source(
                    {
                        "requested_subtitles": {
                            "en": {"filepath": str(outside)}
                        }
                    },
                    job,
                    "My Video",
                    {
                        "language": "en",
                        "requested_format": "srt",
                    },
                )

            self.assertEqual(
                caught.exception.code,
                "subtitle_output_missing",
            )
            self.assertTrue(outside.exists())

    def test_symlink_inside_job_temp_cannot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = root / "job"
            job.mkdir()
            outside = root / "outside.mp4"
            outside.write_bytes(b"outside")
            link = job / "My Video.mp4"

            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks are not available in this environment.")

            with self.assertRaises(YouTubeServiceError) as caught:
                resolve_media_source(
                    {"filepath": str(link)},
                    job,
                    "My Video",
                    "mp4",
                )

            self.assertEqual(caught.exception.code, "output_missing")
            self.assertTrue(outside.exists())


class ProgressAndErrorTests(unittest.TestCase):
    def test_progress_uses_estimated_total_when_exact_total_is_missing(self):
        events = []
        hook = progress_hook(events.append)
        hook(
            {
                "status": "downloading",
                "downloaded_bytes": 25,
                "total_bytes_estimate": 100,
                "speed": 10,
                "eta": 5,
            }
        )
        self.assertEqual(events[0].percent, 25.0)
        self.assertEqual(events[0].total_bytes, 100)
        self.assertTrue(events[0].total_is_estimate)

    def test_postprocessing_errors_are_normalized(self):
        error = normalize_download_error(
            RuntimeError("ffmpeg post-processing failed")
        )
        self.assertEqual(error.code, "post_processing_failed")

    def test_format_and_disk_failures_are_normalized(self):
        format_error = normalize_download_error(
            RuntimeError("Requested format is not available")
        )
        disk_error = normalize_download_error(
            RuntimeError("No space left on device")
        )
        self.assertEqual(format_error.code, "format_unavailable")
        self.assertEqual(disk_error.code, "disk_full")


class SubtitleConversionTests(unittest.TestCase):
    def test_zero_byte_srt_conversion_falls_back_to_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "caption.vtt"
            target = Path(tmp) / "caption.srt"
            source.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHi", encoding="utf-8")
            target.write_bytes(b"")
            fake_process = SimpleNamespace(returncode=0)

            with patch(
                "services.youtube_download.subprocess.run",
                return_value=fake_process,
            ):
                path, output_format = try_convert_subtitle_to_srt(
                    source,
                    target,
                    "/fake/ffmpeg",
                )

            self.assertEqual(path, source)
            self.assertEqual(output_format, "vtt")

    def test_srt_conversion_failure_reports_real_fallback_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "caption.vtt"
            target = Path(tmp) / "caption.srt"
            source.write_text("WEBVTT", encoding="utf-8")
            fake_process = SimpleNamespace(returncode=1)

            with patch(
                "services.youtube_download.subprocess.run",
                return_value=fake_process,
            ):
                path, output_format = try_convert_subtitle_to_srt(
                    source,
                    target,
                    "/fake/ffmpeg",
                )

            self.assertEqual(path, source)
            self.assertEqual(output_format, "vtt")
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
