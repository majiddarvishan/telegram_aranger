import os
import tempfile
import time
import unittest
from pathlib import Path

from services.media_cache import (
    cache_path,
    cleanup_cache,
    is_fresh,
    is_valid_cached_file,
    safe_file_name,
)


class MediaCacheTests(unittest.TestCase):
    def test_safe_file_name_sanitizes_and_adds_extension(self):
        self.assertEqual(
            safe_file_name("../My Video", "video_1", "video/mp4"),
            "My_Video.mp4",
        )

    def test_cache_path_isolated_by_account_chat_and_message(self):
        first = cache_path("/tmp/cache", 1, -100, 10, "video", "clip.mp4")
        second = cache_path("/tmp/cache", 2, -100, 10, "video", "clip.mp4")
        third = cache_path("/tmp/cache", 1, -101, 10, "video", "clip.mp4")
        fourth = cache_path("/tmp/cache", 1, -100, 11, "video", "clip.mp4")

        self.assertNotEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertNotEqual(first, fourth)

    def test_is_fresh_respects_ttl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.bin"
            path.write_bytes(b"x")

            self.assertTrue(is_fresh(path, 1))

            old = time.time() - 7200
            os.utime(path, (old, old))
            self.assertFalse(is_fresh(path, 1))

    def test_valid_cache_requires_expected_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(b"12345")

            self.assertTrue(is_valid_cached_file(path, ttl_hours=1, expected_size=5))
            self.assertFalse(is_valid_cached_file(path, ttl_hours=1, expected_size=10))

    def test_cleanup_removes_interrupted_part_files_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            part_file = root / ".video.mp4.deadbeef.part"
            fresh_file = root / "video.mp4"
            part_file.write_bytes(b"partial")
            fresh_file.write_bytes(b"complete")

            cleanup_cache(tmp, ttl_hours=24, max_megabytes=100)

            self.assertFalse(part_file.exists())
            self.assertTrue(fresh_file.exists())

    def test_cleanup_removes_expired_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_file = root / "old.bin"
            fresh_file = root / "fresh.bin"
            old_file.write_bytes(b"old")
            fresh_file.write_bytes(b"fresh")

            old = time.time() - 7200
            os.utime(old_file, (old, old))

            cleanup_cache(tmp, ttl_hours=1, max_megabytes=100)

            self.assertFalse(old_file.exists())
            self.assertTrue(fresh_file.exists())

    def test_cleanup_enforces_size_limit_oldest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            oldest = root / "oldest.bin"
            newest = root / "newest.bin"
            oldest.write_bytes(b"a" * (700 * 1024))
            newest.write_bytes(b"b" * (700 * 1024))

            old = time.time() - 100
            os.utime(oldest, (old, old))

            cleanup_cache(tmp, ttl_hours=0, max_megabytes=1)

            self.assertFalse(oldest.exists())
            self.assertTrue(newest.exists())


if __name__ == "__main__":
    unittest.main()
