import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.download_paths import (
    DownloadPathError,
    sanitize_youtube_title,
    select_output_group,
    validate_save_directory,
)


class TitleSanitizationTests(unittest.TestCase):
    def test_preserves_unicode_and_replaces_cross_platform_invalid_characters(self):
        self.assertEqual(
            sanitize_youtube_title('  My: "Video" / تست? *  '),
            "My Video تست",
        )

    def test_avoids_windows_reserved_device_names(self):
        self.assertEqual(sanitize_youtube_title("CON"), "_CON")
        self.assertEqual(sanitize_youtube_title("nul.txt"), "_nul.txt")

    def test_empty_title_uses_readable_fallback(self):
        self.assertEqual(sanitize_youtube_title(" . "), "YouTube Video")

    def test_truncates_long_names(self):
        value = sanitize_youtube_title("x" * 300)
        self.assertEqual(len(value), 160)
        self.assertLessEqual(
            len(value.encode("utf-16-le")) // 2,
            160,
        )

    def test_truncates_supplementary_unicode_by_utf16_units(self):
        value = sanitize_youtube_title("😀" * 100)
        self.assertEqual(len(value), 80)
        self.assertEqual(
            len(value.encode("utf-16-le")) // 2,
            160,
        )

    def test_truncation_does_not_create_windows_reserved_name(self):
        value = sanitize_youtube_title("CONXYZ", max_length=3)
        self.assertNotEqual(value.upper(), "CON")
        self.assertTrue(value.startswith("_"))


class SaveDirectoryValidationTests(unittest.TestCase):
    def test_requires_absolute_existing_writable_directory(self):
        with self.assertRaisesRegex(DownloadPathError, "absolute path"):
            validate_save_directory("relative/path")

        with tempfile.TemporaryDirectory() as tmp:
            resolved = validate_save_directory(tmp)
            self.assertEqual(resolved, Path(tmp).resolve())

    def test_missing_directory_requires_explicit_create_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "new" / "youtube"

            with self.assertRaises(DownloadPathError) as caught:
                validate_save_directory(target)
            self.assertEqual(caught.exception.code, "save_directory_missing")

            resolved = validate_save_directory(target, create=True)
            self.assertTrue(resolved.is_dir())

    def test_allowed_roots_accept_child_and_reject_outside_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "allowed"
            inside = root / "user-a"
            outside = Path(tmp) / "outside"
            inside.mkdir(parents=True)
            outside.mkdir()

            self.assertEqual(
                validate_save_directory(inside, allowed_roots=[root]),
                inside.resolve(),
            )

            with self.assertRaises(DownloadPathError) as caught:
                validate_save_directory(outside, allowed_roots=[root])
            self.assertEqual(caught.exception.code, "save_directory_not_allowed")

    def test_symlink_cannot_escape_allowed_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "allowed"
            outside = Path(tmp) / "outside"
            root.mkdir()
            outside.mkdir()
            link = root / "escape"

            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Directory symlinks are not available on this platform.")

            with self.assertRaises(DownloadPathError) as caught:
                validate_save_directory(link, allowed_roots=[root])
            self.assertEqual(caught.exception.code, "save_directory_not_allowed")

    def test_writable_probe_failure_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "utils.download_paths.tempfile.NamedTemporaryFile",
                side_effect=PermissionError("denied"),
            ):
                with self.assertRaises(DownloadPathError) as caught:
                    validate_save_directory(tmp)

            self.assertEqual(
                caught.exception.code,
                "save_directory_not_writable",
            )


class OutputGroupTests(unittest.TestCase):
    def test_media_and_subtitle_share_the_same_sanitized_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            group = select_output_group(
                tmp,
                "My: Video?",
                "mp4",
                "srt",
            )

            self.assertEqual(group.basename, "My Video")
            self.assertEqual(group.media_path.name, "My Video.mp4")
            self.assertEqual(group.subtitle_path.name, "My Video.srt")

    def test_collision_suffix_is_selected_for_the_complete_output_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "My Video.mp4").write_bytes(b"x")
            (root / "My Video (2).srt").write_text("existing", encoding="utf-8")

            group = select_output_group(
                root,
                "My Video",
                ".mp4",
                ".srt",
            )

            self.assertEqual(group.basename, "My Video (3)")
            self.assertEqual(group.media_path.name, "My Video (3).mp4")
            self.assertEqual(group.subtitle_path.name, "My Video (3).srt")

    def test_does_not_require_subtitle_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            group = select_output_group(tmp, "Audio Track", "mp3")
            self.assertEqual(group.media_path.name, "Audio Track.mp3")
            self.assertIsNone(group.subtitle_path)

    def test_long_unicode_basename_stays_within_windows_component_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            group = select_output_group(
                tmp,
                "😀" * 200,
                "mp4",
                "srt",
            )

            for path in group.paths:
                units = len(path.name.encode("utf-16-le")) // 2
                self.assertLess(units, 255)

    def test_rejects_extension_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DownloadPathError) as caught:
                select_output_group(tmp, "Video", "../mp4")
            self.assertEqual(caught.exception.code, "invalid_output_extension")


if __name__ == "__main__":
    unittest.main()
