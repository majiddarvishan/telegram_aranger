from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
import sys
from typing import Any, Iterable


LIVE_MODES = {"video_audio", "audio_only"}


def load_reports(paths: Iterable[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    reports: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for raw_path in paths:
        path = Path(raw_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(
                {
                    "path": str(path),
                    "error_type": type(exc).__name__,
                    "message": "Validation report could not be read.",
                }
            )
            continue

        if not isinstance(payload, dict):
            errors.append(
                {
                    "path": str(path),
                    "error_type": "InvalidReport",
                    "message": "Validation report root must be a JSON object.",
                }
            )
            continue

        payload = dict(payload)
        payload["_report_file"] = str(path)
        reports.append(payload)

    return reports, errors


def _passed(report: dict[str, Any]) -> bool:
    return report.get("status") == "passed"


def _mode(report: dict[str, Any]) -> str:
    return str(report.get("mode") or "")


def _request(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("request")
    return value if isinstance(value, dict) else {}


def _checks(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("checks")
    return value if isinstance(value, dict) else {}


def _environment(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("environment")
    return value if isinstance(value, dict) else {}


def _policy(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("policy")
    return value if isinstance(value, dict) else {}


def _is_successful_live(report: dict[str, Any]) -> bool:
    return (
        _passed(report)
        and _mode(report) in LIVE_MODES
        and _checks(report).get("all_passed") is True
    )


def summarize_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    usable_commit_values = {
        str(_environment(report).get("commit_sha"))
        for report in reports
        if _environment(report).get("commit_sha")
        not in {None, "", "unknown", "local"}
    }
    commits = sorted(usable_commit_values)
    reports_missing_source_commit = sum(
        1
        for report in reports
        if _environment(report).get("commit_sha")
        in {None, "", "unknown", "local"}
    )
    source_commit_complete = (
        bool(reports)
        and reports_missing_source_commit == 0
    )

    coverage = {
        "preflight": any(
            _passed(report) and _mode(report) == "preflight"
            for report in reports
        ),
        "public_inspect": any(
            _passed(report)
            and _mode(report) == "inspect"
            and _policy(report).get("blocked") is False
            and bool(report.get("video_id"))
            for report in reports
        ),
        "video_audio": any(
            _is_successful_live(report)
            and _mode(report) == "video_audio"
            for report in reports
        ),
        "audio_only": any(
            _is_successful_live(report)
            and _mode(report) == "audio_only"
            for report in reports
        ),
        "manual_subtitle": any(
            _is_successful_live(report)
            and _request(report).get("subtitle_source") == "manual"
            and _checks(report).get("subtitle_presence_matches_request") is True
            and _checks(report).get("subtitle_source_matches_request") is True
            and _checks(report).get("subtitle_language_matches_request") is True
            for report in reports
        ),
        "automatic_caption": any(
            _is_successful_live(report)
            and _request(report).get("subtitle_source") == "automatic"
            and _checks(report).get("subtitle_presence_matches_request") is True
            and _checks(report).get("subtitle_source_matches_request") is True
            and _checks(report).get("subtitle_language_matches_request") is True
            for report in reports
        ),
        "collision_second_run": any(
            _is_successful_live(report)
            and _request(report).get("expect_collision") is True
            and _checks(report).get("collision_expectation_met") is True
            and isinstance(_checks(report).get("collision_number"), int)
            and _checks(report).get("collision_number") >= 2
            for report in reports
        ),
        "save_directory_live": any(
            _is_successful_live(report)
            and _checks(report).get("media_within_save_directory") is True
            for report in reports
        ),
        "windows_live_download": any(
            _is_successful_live(report)
            and str(_environment(report).get("platform") or "").lower()
            == "windows"
            for report in reports
        ),
        "docker_live_download": any(
            _is_successful_live(report)
            and _environment(report).get("docker") is True
            for report in reports
        ),
        "public_acknowledged_download": any(
            _is_successful_live(report)
            and _request(report).get("acknowledged") is True
            and _policy(report).get("blocked") is False
            and _policy(report).get("requires_acknowledgement") is True
            for report in reports
        ),
        "structured_failure_report": any(
            report.get("status") == "failed"
            and isinstance(report.get("error"), dict)
            and bool(report["error"].get("code"))
            for report in reports
        ),
    }

    core_keys = (
        "preflight",
        "public_inspect",
        "video_audio",
        "audio_only",
        "manual_subtitle",
        "automatic_caption",
        "collision_second_run",
        "save_directory_live",
    )
    release_runner_keys = (
        *core_keys,
        "windows_live_download",
        "docker_live_download",
        "public_acknowledged_download",
        "structured_failure_report",
    )
    core_runner_coverage_complete = all(
        coverage[key] for key in core_keys
    )
    release_runner_coverage_complete = all(
        coverage[key] for key in release_runner_keys
    )
    release_runner_evidence_ready = (
        release_runner_coverage_complete
        and source_commit_complete
        and len(commits) == 1
    )

    return {
        "reports_total": len(reports),
        "reports_passed": sum(1 for report in reports if _passed(report)),
        "reports_failed": sum(
            1 for report in reports if report.get("status") == "failed"
        ),
        "source_commits": commits,
        "reports_missing_source_commit": reports_missing_source_commit,
        "source_commit_complete": source_commit_complete,
        "single_source_commit": (
            source_commit_complete and len(commits) == 1
        ),
        "coverage": coverage,
        "core_runner_coverage_complete": core_runner_coverage_complete,
        "release_runner_coverage_complete": release_runner_coverage_complete,
        "release_runner_evidence_ready": release_runner_evidence_ready,
        "manual_only_remaining": [
            "Light theme visual review",
            "Dark theme visual review",
            "Narrow/responsive visual review",
            "Real Streamlit warning/error presentation",
            "Final merge/release review",
        ],
    }


def _expand_patterns(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            paths.extend(matches)
        else:
            paths.append(pattern)
    return sorted(dict.fromkeys(paths))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize Telegram Harbor YouTube manual-validation JSON reports "
            "without performing any network requests."
        )
    )
    parser.add_argument(
        "reports",
        nargs="+",
        help="Report files or shell-style glob patterns.",
    )
    parser.add_argument(
        "--require-core",
        action="store_true",
        help="Return non-zero unless all core runner scenarios are covered.",
    )
    parser.add_argument(
        "--require-release-ready",
        action="store_true",
        help=(
            "Return non-zero unless all runner/platform/policy scenarios are "
            "covered by reports from one concrete source commit."
        ),
    )
    args = parser.parse_args()

    paths = _expand_patterns(args.reports)
    reports, errors = load_reports(paths)
    summary = summarize_reports(reports)
    summary["read_errors"] = errors

    print(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    if errors:
        return 2
    if args.require_core and not summary["core_runner_coverage_complete"]:
        return 4
    if (
        args.require_release_ready
        and not summary["release_runner_evidence_ready"]
    ):
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
