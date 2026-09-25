import json
import tempfile
import unittest
from pathlib import Path

from scripts.youtube_validation_summary import (
    load_reports,
    summarize_reports,
)


def report(
    *,
    mode,
    status="passed",
    commit="abc123",
    platform="Linux",
    docker=False,
    request=None,
    checks=None,
    policy=None,
    video_id="BaW_jenozKc",
):
    return {
        "mode": mode,
        "status": status,
        "video_id": video_id,
        "environment": {
            "commit_sha": commit,
            "platform": platform,
            "docker": docker,
        },
        "request": request or {
            "acknowledged": mode in {"video_audio", "audio_only"},
            "subtitle_source": None,
            "expect_collision": False,
        },
        "checks": checks or (
            {
                "all_passed": True,
                "media_within_save_directory": True,
                "subtitle_presence_matches_request": True,
                "subtitle_source_matches_request": True,
                "subtitle_language_matches_request": True,
                "collision_expectation_met": True,
                "collision_number": None,
            }
            if mode in {"video_audio", "audio_only"}
            else {}
        ),
        "policy": policy or {
            "blocked": False,
            "requires_acknowledgement": True,
        },
    }


class YouTubeValidationSummaryTests(unittest.TestCase):
    def test_core_coverage_is_complete_from_matching_reports(self):
        reports = [
            report(mode="preflight"),
            report(mode="inspect"),
            report(mode="video_audio"),
            report(mode="audio_only"),
            report(
                mode="video_audio",
                request={
                    "acknowledged": True,
                    "subtitle_source": "manual",
                    "expect_collision": False,
                },
            ),
            report(
                mode="video_audio",
                request={
                    "acknowledged": True,
                    "subtitle_source": "automatic",
                    "expect_collision": False,
                },
            ),
            report(
                mode="video_audio",
                request={
                    "acknowledged": True,
                    "subtitle_source": "manual",
                    "expect_collision": True,
                },
                checks={
                    "all_passed": True,
                    "media_within_save_directory": True,
                    "subtitle_presence_matches_request": True,
                    "subtitle_source_matches_request": True,
                    "subtitle_language_matches_request": True,
                    "collision_expectation_met": True,
                    "collision_number": 2,
                },
            ),
        ]

        summary = summarize_reports(reports)

        self.assertTrue(summary["core_runner_coverage_complete"])
        self.assertTrue(summary["coverage"]["preflight"])
        self.assertTrue(summary["coverage"]["public_inspect"])
        self.assertTrue(summary["coverage"]["video_audio"])
        self.assertTrue(summary["coverage"]["audio_only"])
        self.assertTrue(summary["coverage"]["manual_subtitle"])
        self.assertTrue(summary["coverage"]["automatic_caption"])
        self.assertTrue(summary["coverage"]["collision_second_run"])
        self.assertTrue(summary["coverage"]["save_directory_live"])
        self.assertTrue(summary["single_source_commit"])
        self.assertEqual(summary["source_commits"], ["abc123"])

    def test_windows_and_docker_require_successful_live_downloads(self):
        reports = [
            report(
                mode="preflight",
                platform="Windows",
            ),
            report(
                mode="preflight",
                docker=True,
            ),
        ]
        summary = summarize_reports(reports)
        self.assertFalse(summary["coverage"]["windows_live_download"])
        self.assertFalse(summary["coverage"]["docker_live_download"])

        reports.extend(
            [
                report(
                    mode="video_audio",
                    platform="Windows",
                ),
                report(
                    mode="audio_only",
                    docker=True,
                ),
            ]
        )
        summary = summarize_reports(reports)
        self.assertTrue(summary["coverage"]["windows_live_download"])
        self.assertTrue(summary["coverage"]["docker_live_download"])

    def test_collision_coverage_requires_explicit_expectation_and_suffix(self):
        no_expectation = report(mode="video_audio")
        bad_collision = report(
            mode="video_audio",
            request={
                "acknowledged": True,
                "subtitle_source": None,
                "expect_collision": True,
            },
            checks={
                "all_passed": False,
                "media_within_save_directory": True,
                "collision_expectation_met": False,
                "collision_number": None,
            },
        )
        good_collision = report(
            mode="video_audio",
            request={
                "acknowledged": True,
                "subtitle_source": None,
                "expect_collision": True,
            },
            checks={
                "all_passed": True,
                "media_within_save_directory": True,
                "collision_expectation_met": True,
                "collision_number": 3,
            },
        )

        self.assertFalse(
            summarize_reports([no_expectation])["coverage"][
                "collision_second_run"
            ]
        )
        self.assertFalse(
            summarize_reports([bad_collision])["coverage"][
                "collision_second_run"
            ]
        )
        self.assertTrue(
            summarize_reports([good_collision])["coverage"][
                "collision_second_run"
            ]
        )

    def test_multiple_commits_are_reported_as_mixed_evidence(self):
        summary = summarize_reports(
            [
                report(mode="preflight", commit="aaa"),
                report(mode="inspect", commit="bbb"),
            ]
        )
        self.assertEqual(summary["source_commits"], ["aaa", "bbb"])
        self.assertFalse(summary["single_source_commit"])

    def test_structured_failure_is_counted_without_satisfying_live_modes(self):
        failed = report(
            mode="video_audio",
            status="failed",
        )
        failed["error"] = {
            "code": "format_unavailable",
            "message": "Format unavailable.",
        }
        summary = summarize_reports([failed])
        self.assertEqual(summary["reports_failed"], 1)
        self.assertTrue(summary["coverage"]["structured_failure_report"])
        self.assertFalse(summary["coverage"]["video_audio"])

    def test_load_reports_surfaces_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "good.json"
            bad = root / "bad.json"
            good.write_text(
                json.dumps(report(mode="preflight")),
                encoding="utf-8",
            )
            bad.write_text("{not-json", encoding="utf-8")

            reports, errors = load_reports(
                [str(good), str(bad)]
            )

        self.assertEqual(len(reports), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["error_type"], "JSONDecodeError")


if __name__ == "__main__":
    unittest.main()
