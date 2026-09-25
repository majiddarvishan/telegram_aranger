from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.youtube_download import (  # noqa: E402
    DownloadProgress,
    DownloadRequest,
    SubtitleSelection,
    download_video,
)
from services.youtube_policy import evaluate_download_policy  # noqa: E402
from services.youtube_service import (  # noqa: E402
    YouTubeServiceError,
    detect_ffmpeg,
    inspect_video,
    validate_youtube_url,
)
from utils.download_paths import (  # noqa: E402
    DownloadPathError,
    sanitize_youtube_title,
    validate_save_directory,
)


MODES = ("preflight", "inspect", "video_audio", "audio_only")
QUALITIES = ("best", "max_1080p", "max_720p", "max_480p")
SUBTITLE_SOURCES = ("manual", "automatic")


def _detect_commit_sha() -> str | None:
    configured = os.getenv("TELEGRAM_HARBOR_BUILD_SHA", "").strip()
    if configured and configured.lower() not in {"unknown", "local"}:
        return configured

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return configured or None

    value = completed.stdout.strip()
    return value or configured or None


def _environment_summary() -> dict[str, Any]:
    version_path = ROOT / "VERSION"
    try:
        app_version = version_path.read_text(encoding="utf-8").strip()
    except OSError:
        app_version = None

    return {
        "platform": platform.system() or None,
        "platform_release": platform.release() or None,
        "machine": platform.machine() or None,
        "python_version": platform.python_version(),
        "docker": Path("/.dockerenv").exists(),
        "app_version": app_version,
        "commit_sha": _detect_commit_sha(),
    }


def _request_summary(args) -> dict[str, Any]:
    return {
        "mode": args.mode,
        "quality": (
            "best"
            if args.mode == "audio_only"
            else args.quality
        ),
        "save_directory": args.save_directory,
        "create_directory": bool(args.create_directory),
        "allowed_roots": list(args.allowed_root),
        "subtitle_language": args.subtitle_language,
        "subtitle_source": args.subtitle_source,
        "acknowledged": bool(args.acknowledge),
        "expect_collision": bool(
            getattr(args, "expect_collision", False)
        ),
    }


def _safe_metadata_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    subtitles = metadata.get("subtitles")
    if not isinstance(subtitles, list):
        subtitles = []

    return {
        "video_id": metadata.get("video_id"),
        "title": metadata.get("title"),
        "channel": metadata.get("channel") or metadata.get("uploader"),
        "duration_seconds": metadata.get("duration_seconds"),
        "availability": metadata.get("availability"),
        "age_limit": metadata.get("age_limit"),
        "is_live": metadata.get("is_live"),
        "live_status": metadata.get("live_status"),
        "has_drm": metadata.get("has_drm"),
        "estimated_size_bytes": metadata.get("estimated_size_bytes"),
        "format_count": len(metadata.get("formats") or []),
        "subtitle_tracks": [
            {
                "language": track.get("language"),
                "name": track.get("name"),
                "source": track.get("source"),
                "formats": track.get("formats") or [],
                "preferred_format": track.get("preferred_format"),
            }
            for track in subtitles
            if isinstance(track, dict)
        ],
    }


def _progress_record(event: DownloadProgress) -> dict[str, Any]:
    return {
        "phase": event.phase,
        "status": event.status,
        "percent": event.percent,
        "downloaded_bytes": event.downloaded_bytes,
        "total_bytes": event.total_bytes,
        "total_is_estimate": event.total_is_estimate,
        "speed_bytes_per_second": event.speed_bytes_per_second,
        "eta_seconds": event.eta_seconds,
        "detail": event.detail,
        "final_output_path": event.final_output_path,
    }


def _result_checks(
    result,
    save_directory: str,
    progress_events: list[dict[str, Any]],
    *,
    subtitle_expected: bool = False,
    expected_subtitle_source: str | None = None,
    expected_subtitle_language: str | None = None,
    expect_collision: bool = False,
) -> dict[str, Any]:
    root = Path(save_directory).expanduser().resolve(strict=True)
    media = Path(result.media_path).resolve(strict=False)
    subtitle = (
        Path(result.subtitle_path).resolve(strict=False)
        if result.subtitle_path
        else None
    )

    media_exists = media.is_file()
    subtitle_exists = (
        subtitle.is_file()
        if subtitle is not None
        else (False if subtitle_expected else None)
    )
    media_contained = media.parent == root or root in media.parents
    subtitle_contained = (
        subtitle.parent == root or root in subtitle.parents
        if subtitle is not None
        else (False if subtitle_expected else None)
    )
    matched_basename = (
        media.stem == subtitle.stem
        if subtitle is not None
        else (False if subtitle_expected else None)
    )
    subtitle_presence_matches_request = (
        (subtitle is not None) == subtitle_expected
    )
    subtitle_source_matches_request = (
        result.subtitle_source == expected_subtitle_source
        if subtitle_expected
        else result.subtitle_source is None
    )
    subtitle_language_matches_request = (
        result.subtitle_language == expected_subtitle_language
        if subtitle_expected
        else result.subtitle_language is None
    )
    completed_progress = any(
        event.get("phase") == "completed"
        and event.get("status") == "finished"
        for event in progress_events
    )

    expected_title_base = sanitize_youtube_title(result.title)
    stem = media.stem
    collision_number = None
    collision_prefix = expected_title_base + " ("
    if stem.startswith(collision_prefix) and stem.endswith(")"):
        raw_number = stem[len(collision_prefix) : -1]
        if raw_number.isdigit() and int(raw_number) >= 2:
            collision_number = int(raw_number)

    title_based_name = (
        stem == expected_title_base or collision_number is not None
    )
    collision_expectation_met = (
        collision_number is not None
        if expect_collision
        else True
    )
    expected_media_suffix = ".mp3" if result.mode == "audio_only" else ".mp4"
    media_extension_matches_mode = media.suffix.lower() == expected_media_suffix
    subtitle_extension_matches_report = (
        subtitle.suffix.lower()
        == f".{str(result.subtitle_format).lower().lstrip('.')}"
        if subtitle is not None and result.subtitle_format
        else not subtitle_expected
    )

    boolean_checks = [
        media_exists,
        media_contained,
        completed_progress,
        title_based_name,
        collision_expectation_met,
        media_extension_matches_mode,
        subtitle_presence_matches_request,
        subtitle_source_matches_request,
        subtitle_language_matches_request,
        subtitle_extension_matches_report,
    ]
    if subtitle_expected:
        boolean_checks.extend(
            [
                bool(subtitle_exists),
                bool(subtitle_contained),
                bool(matched_basename),
            ]
        )

    return {
        "media_exists": media_exists,
        "subtitle_exists": subtitle_exists,
        "media_within_save_directory": media_contained,
        "subtitle_within_save_directory": subtitle_contained,
        "media_subtitle_basename_match": matched_basename,
        "completed_progress_observed": completed_progress,
        "title_based_output_name": title_based_name,
        "collision_number": collision_number,
        "collision_expectation_met": collision_expectation_met,
        "media_extension_matches_mode": media_extension_matches_mode,
        "subtitle_presence_matches_request": subtitle_presence_matches_request,
        "subtitle_source_matches_request": subtitle_source_matches_request,
        "subtitle_language_matches_request": subtitle_language_matches_request,
        "subtitle_extension_matches_report": subtitle_extension_matches_report,
        "all_passed": all(boolean_checks),
    }


def _write_report(report: dict[str, Any], report_file: str | None) -> None:
    text = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
    print(text)
    if not report_file:
        return

    path = Path(report_file).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    print(f"Report written to: {path}", file=sys.stderr)


def _subtitle_selection(args, metadata: dict[str, Any]) -> SubtitleSelection | None:
    if not args.subtitle_language:
        return None

    tracks = metadata.get("subtitles")
    if not isinstance(tracks, list):
        tracks = []

    source = args.subtitle_source
    candidates = [
        track
        for track in tracks
        if isinstance(track, dict)
        and str(track.get("language")) == args.subtitle_language
        and (source is None or str(track.get("source")) == source)
    ]

    if not candidates:
        raise YouTubeServiceError(
            "subtitle_unavailable",
            "Requested manual-validation subtitle/caption track was not found.",
        )

    if source is None and len(candidates) > 1:
        available = ", ".join(
            sorted({str(track.get("source")) for track in candidates})
        )
        raise YouTubeServiceError(
            "subtitle_source_required",
            "Multiple subtitle sources are available for this language; "
            f"choose --subtitle-source from: {available}.",
        )

    selected = candidates[0]
    return SubtitleSelection(
        language=str(selected.get("language")),
        source=str(selected.get("source")),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Manual/live YouTube V1 validation helper for Telegram Harbor. "
            "This script is intentionally not used by CI."
        )
    )
    parser.add_argument(
        "--url",
        help="One public YouTube video URL. Not required for preflight mode.",
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="inspect",
        help="Run offline preflight, inspect metadata, or execute one download mode.",
    )
    parser.add_argument(
        "--quality",
        choices=QUALITIES,
        default="best",
        help="Video quality preset. Audio-only ignores this and uses best audio.",
    )
    parser.add_argument(
        "--save-directory",
        help="Absolute host path required for download modes.",
    )
    parser.add_argument(
        "--create-directory",
        action="store_true",
        help="Explicitly create a missing save directory before download.",
    )
    parser.add_argument(
        "--allowed-root",
        action="append",
        default=[],
        help="Optional allowed root. Repeat for multiple roots.",
    )
    parser.add_argument(
        "--subtitle-language",
        help="Optional subtitle/caption language code from Inspect output.",
    )
    parser.add_argument(
        "--subtitle-source",
        choices=SUBTITLE_SOURCES,
        help="manual or automatic; required if the language has both.",
    )
    parser.add_argument(
        "--acknowledge",
        action="store_true",
        help="Required for download modes; acknowledges the rights/service notice.",
    )
    parser.add_argument(
        "--expect-collision",
        action="store_true",
        help=(
            "For an intentional second-run collision test, require the final "
            "title-based output to use a numeric suffix such as (2)."
        ),
    )
    parser.add_argument(
        "--report-file",
        help=(
            "Optional JSON report path. Prefer validation-reports/...; "
            "that directory is gitignored."
        ),
    )
    return parser


def run(args) -> tuple[dict[str, Any], int]:
    started_at = datetime.now(timezone.utc)
    ffmpeg = detect_ffmpeg()
    progress_events: list[dict[str, Any]] = []

    report: dict[str, Any] = {
        "started_at": started_at.isoformat(),
        "mode": args.mode,
        "quality": args.quality,
        "video_id": None,
        "request": _request_summary(args),
        "environment": _environment_summary(),
        "ffmpeg": ffmpeg.as_dict(),
        "status": "started",
    }

    try:
        if args.mode == "preflight":
            if not args.save_directory:
                raise DownloadPathError(
                    "save_directory_required",
                    "--save-directory is required for preflight mode.",
                )

            validated_directory = validate_save_directory(
                args.save_directory,
                allowed_roots=tuple(args.allowed_root),
                create=bool(args.create_directory),
            )
            report["preflight"] = {
                "save_directory": str(validated_directory),
                "save_directory_valid": True,
                "ffmpeg_fully_available": ffmpeg.fully_available,
            }
            report["status"] = (
                "passed" if ffmpeg.fully_available else "failed"
            )
            if not ffmpeg.fully_available:
                report["error"] = {
                    "code": "ffmpeg_unavailable",
                    "message": (
                        "FFmpeg and FFprobe are required for YouTube V1 downloads."
                    ),
                }
            return report, 0 if ffmpeg.fully_available else 4

        validated = validate_youtube_url(args.url or "")
        report["video_id"] = validated["video_id"]

        metadata = inspect_video(validated["url"])
        report["metadata"] = _safe_metadata_summary(metadata)

        policy = evaluate_download_policy(
            metadata,
            acknowledged=bool(args.acknowledge),
        )
        report["policy"] = policy.as_dict()

        if args.mode == "inspect":
            report["status"] = "passed"
            return report, 0

        if not args.save_directory:
            raise DownloadPathError(
                "save_directory_required",
                "--save-directory is required for download modes.",
            )

        if args.create_directory:
            validate_save_directory(
                args.save_directory,
                allowed_roots=tuple(args.allowed_root),
                create=True,
            )

        subtitle = _subtitle_selection(args, metadata)

        def on_progress(event: DownloadProgress) -> None:
            record = _progress_record(event)
            progress_events.append(record)
            phase = record["phase"]
            percent = record["percent"]
            detail = record["detail"] or ""
            percent_text = (
                f" {percent:.1f}%"
                if isinstance(percent, (int, float))
                else ""
            )
            print(
                f"[{phase}]{percent_text} {detail}".rstrip(),
                file=sys.stderr,
            )

        result = download_video(
            DownloadRequest(
                url=validated["url"],
                save_directory=args.save_directory,
                mode=args.mode,
                quality=("best" if args.mode == "audio_only" else args.quality),
                subtitle=subtitle,
                acknowledged=bool(args.acknowledge),
            ),
            metadata,
            allowed_roots=tuple(args.allowed_root),
            progress_callback=on_progress,
        )

        report["progress"] = {
            "event_count": len(progress_events),
            "phases": list(
                dict.fromkeys(event["phase"] for event in progress_events)
            ),
            "last_event": progress_events[-1] if progress_events else None,
        }
        report["result"] = result.as_dict()
        report["checks"] = _result_checks(
            result,
            args.save_directory,
            progress_events,
            subtitle_expected=subtitle is not None,
            expected_subtitle_source=(
                subtitle.source if subtitle is not None else None
            ),
            expected_subtitle_language=(
                subtitle.language if subtitle is not None else None
            ),
            expect_collision=bool(
                getattr(args, "expect_collision", False)
            ),
        )
        report["status"] = (
            "passed"
            if report["checks"]["all_passed"]
            else "failed"
        )
        return report, 0 if report["checks"]["all_passed"] else 4

    except (YouTubeServiceError, DownloadPathError) as exc:
        report["status"] = "failed"
        report["error"] = {
            "code": getattr(exc, "code", "validation_error"),
            "message": str(exc),
        }
        return report, 2
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = {
            "code": "unexpected_error",
            "message": "Unexpected validation failure.",
            "exception_type": type(exc).__name__,
        }
        return report, 3
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    report, exit_code = run(args)
    _write_report(report, args.report_file)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
