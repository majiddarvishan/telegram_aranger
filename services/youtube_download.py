from __future__ import annotations

from dataclasses import asdict, dataclass
import errno
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable, Mapping, Protocol

from services.youtube_policy import evaluate_download_policy
from services.youtube_service import (
    FFmpegCapability,
    YouTubeProxyConfig,
    YouTubeServiceError,
    detect_ffmpeg,
    normalize_downloader_error,
    validate_youtube_url,
)
from utils.download_paths import (
    DownloadPathError,
    OutputGroup,
    sanitize_youtube_title,
    select_output_group,
    validate_save_directory,
)


VALID_MODES = {"video_audio", "audio_only"}
QUALITY_HEIGHTS = {
    "best": None,
    "max_1080p": 1080,
    "max_720p": 720,
    "max_480p": 480,
}


@dataclass(frozen=True)
class SubtitleSelection:
    language: str
    source: str  # manual | automatic


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    save_directory: str
    mode: str = "video_audio"
    quality: str = "best"
    subtitle: SubtitleSelection | None = None
    acknowledged: bool = False
    proxy: YouTubeProxyConfig | None = None


@dataclass(frozen=True)
class DownloadProgress:
    phase: str
    status: str
    percent: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    total_is_estimate: bool = False
    speed_bytes_per_second: float | None = None
    eta_seconds: float | None = None
    detail: str | None = None
    final_output_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DownloadResult:
    video_id: str
    title: str
    mode: str
    quality: str
    media_path: str
    subtitle_path: str | None
    subtitle_format: str | None
    subtitle_source: str | None
    subtitle_language: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DownloadBackend(Protocol):
    def download(self, url: str, options: Mapping[str, Any]) -> Mapping[str, Any]:
        """Download one media item and return downloader info."""


class _QuietLogger:
    def debug(self, _message: str) -> None:
        pass

    def info(self, _message: str) -> None:
        pass

    def warning(self, _message: str) -> None:
        pass

    def error(self, _message: str) -> None:
        pass


class YtDlpDownloadBackend:
    """yt-dlp adapter used only by the service layer."""

    def download(self, url: str, options: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover - dependency is installed in CI
            raise YouTubeServiceError(
                "downloader_unavailable",
                "YouTube downloader dependency is not installed.",
            ) from exc

        try:
            with yt_dlp.YoutubeDL(dict(options)) as downloader:
                info = downloader.extract_info(url, download=True)
        except Exception as exc:
            raise normalize_download_error(exc) from exc

        if not isinstance(info, Mapping):
            raise YouTubeServiceError(
                "download_failed",
                "YouTube download did not return output information.",
            )
        return info


def download_video(
    request: DownloadRequest,
    metadata: Mapping[str, Any],
    *,
    allowed_roots: tuple[str, ...] = (),
    backend: DownloadBackend | None = None,
    ffmpeg: FFmpegCapability | None = None,
    progress_callback: Callable[[DownloadProgress], None] | None = None,
) -> DownloadResult:
    """Execute one validated V1 download job."""
    validated = validate_youtube_url(request.url)
    metadata_video_id = str(metadata.get("video_id") or "").strip()
    if (
        metadata_video_id
        and metadata_video_id != validated["video_id"]
    ):
        raise YouTubeServiceError(
            "metadata_video_mismatch",
            "Inspected YouTube metadata does not match the requested video.",
        )

    mode = validate_mode(request.mode)
    quality = validate_quality(request.quality)
    save_directory = validate_save_directory(
        request.save_directory,
        allowed_roots=allowed_roots,
    )

    policy = evaluate_download_policy(
        metadata,
        acknowledged=request.acknowledged,
    )
    if policy.blocked:
        raise YouTubeServiceError(
            policy.block_code or "download_blocked",
            policy.block_message or "This video cannot be downloaded.",
            access_restricted=True,
        )
    if not policy.can_download:
        raise YouTubeServiceError(
            "acknowledgement_required",
            "You must acknowledge the rights/service notice before downloading.",
        )

    capability = ffmpeg or detect_ffmpeg()
    if not capability.fully_available:
        raise YouTubeServiceError(
            "ffmpeg_unavailable",
            "FFmpeg and FFprobe are required for YouTube V1 downloads.",
        )

    title = str(metadata.get("title") or "YouTube Video")
    temp_basename = sanitize_youtube_title(title)
    subtitle_plan = build_subtitle_plan(metadata, request.subtitle)
    media_extension = "mp3" if mode == "audio_only" else "mp4"

    final_group: OutputGroup | None = None
    successful = False
    try:
        with tempfile.TemporaryDirectory(
            prefix=".telegram-harbor-youtube-",
            dir=save_directory,
        ) as temp_root:
            temp_directory = Path(temp_root)
            options = build_download_options(
                temp_directory=temp_directory,
                basename=temp_basename,
                mode=mode,
                quality=quality,
                subtitle_plan=subtitle_plan,
                progress_callback=progress_callback,
                proxy=request.proxy,
            )
            downloader = backend or YtDlpDownloadBackend()

            try:
                info = downloader.download(validated["url"], options)
            except YouTubeServiceError:
                raise
            except Exception as exc:
                raise normalize_download_error(exc) from exc

            downloaded_video_id = str(info.get("id") or "").strip()
            if (
                downloaded_video_id
                and downloaded_video_id != validated["video_id"]
            ):
                raise YouTubeServiceError(
                    "download_video_mismatch",
                    "Downloader output does not match the requested YouTube video.",
                )

            media_source = resolve_media_source(
                info,
                temp_directory,
                temp_basename,
                media_extension,
            )
            if media_source.stat().st_size <= 0:
                raise YouTubeServiceError(
                    "output_empty",
                    "Downloader produced an empty media file.",
                )

            subtitle_source_path: Path | None = None
            actual_subtitle_format: str | None = None
            if subtitle_plan is not None:
                subtitle_source_path = resolve_subtitle_source(
                    info,
                    temp_directory,
                    temp_basename,
                    subtitle_plan,
                )
                if subtitle_source_path.stat().st_size <= 0:
                    raise YouTubeServiceError(
                        "subtitle_output_empty",
                        "Downloader produced an empty subtitle file.",
                    )
                actual_subtitle_format = subtitle_source_path.suffix.lstrip(".").lower()

                if (
                    subtitle_plan["prefer_srt"]
                    and actual_subtitle_format == "vtt"
                    and capability.ffmpeg_path
                ):
                    converted, converted_format = try_convert_subtitle_to_srt(
                        subtitle_source_path,
                        temp_directory / f"{temp_basename}.srt",
                        capability.ffmpeg_path,
                        progress_callback=progress_callback,
                    )
                    subtitle_source_path = converted
                    actual_subtitle_format = converted_format

            final_group = reserve_available_group(
                save_directory,
                title,
                media_extension,
                actual_subtitle_format,
            )

            os.replace(media_source, final_group.media_path)
            if (
                subtitle_source_path is not None
                and final_group.subtitle_path is not None
            ):
                os.replace(subtitle_source_path, final_group.subtitle_path)

            successful = True
            result = DownloadResult(
                video_id=str(metadata.get("video_id") or validated["video_id"]),
                title=title,
                mode=mode,
                quality=quality,
                media_path=str(final_group.media_path),
                subtitle_path=(
                    str(final_group.subtitle_path)
                    if final_group.subtitle_path is not None
                    else None
                ),
                subtitle_format=actual_subtitle_format,
                subtitle_source=(
                    subtitle_plan["source"]
                    if subtitle_plan is not None
                    else None
                ),
                subtitle_language=(
                    subtitle_plan["language"]
                    if subtitle_plan is not None
                    else None
                ),
            )
            emit_progress(
                progress_callback,
                DownloadProgress(
                    phase="completed",
                    status="finished",
                    percent=100.0,
                    final_output_path=result.media_path,
                ),
            )
            return result
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            raise YouTubeServiceError(
                "disk_full",
                "The save directory does not have enough free disk space.",
            ) from exc
        raise
    finally:
        if not successful and final_group is not None:
            cleanup_reserved_group(final_group)


def build_download_options(
    *,
    temp_directory: Path,
    basename: str,
    mode: str,
    quality: str,
    subtitle_plan: Mapping[str, Any] | None,
    progress_callback: Callable[[DownloadProgress], None] | None,
    proxy: YouTubeProxyConfig | None = None,
) -> dict[str, Any]:
    postprocessors: list[dict[str, Any]] = []
    if mode == "audio_only":
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
                "nopostoverwrites": True,
            }
        )
    else:
        postprocessors.append(
            {
                "key": "FFmpegVideoRemuxer",
                "preferedformat": "mp4",
            }
        )

    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "logger": _QuietLogger(),
        "noplaylist": True,
        "overwrites": False,
        "format": format_selector(mode, quality),
        "paths": {
            "home": str(temp_directory),
            "temp": str(temp_directory),
        },
        "outtmpl": {
            "default": str(temp_directory / f"{basename}.%(ext)s"),
            "subtitle": str(temp_directory / f"{basename}.%(ext)s"),
        },
        "postprocessors": postprocessors,
        "progress_hooks": [progress_hook(progress_callback)],
        "postprocessor_hooks": [postprocessor_hook(progress_callback)],
    }

    proxy_url = proxy.proxy_url() if proxy is not None else None
    if proxy_url:
        options["proxy"] = proxy_url

    if mode == "video_audio":
        options["merge_output_format"] = "mp4"
        options["final_ext"] = "mp4"
    else:
        options["final_ext"] = "mp3"

    if subtitle_plan is not None:
        source = subtitle_plan["source"]
        options["writesubtitles"] = source == "manual"
        options["writeautomaticsub"] = source == "automatic"
        options["subtitleslangs"] = [subtitle_plan["language"]]
        options["subtitlesformat"] = subtitle_plan["requested_format"]

    return options


def format_selector(mode: str, quality: str) -> str:
    if mode == "audio_only":
        return "ba/b"

    max_height = QUALITY_HEIGHTS[quality]
    if max_height is None:
        return "bv*+ba/b"
    return f"bv*[height<={max_height}]+ba/b[height<={max_height}]"


def build_subtitle_plan(
    metadata: Mapping[str, Any],
    selection: SubtitleSelection | None,
) -> dict[str, Any] | None:
    if selection is None:
        return None
    if selection.source not in {"manual", "automatic"}:
        raise YouTubeServiceError(
            "subtitle_selection_invalid",
            "Subtitle source must be manual or automatic.",
        )

    tracks = metadata.get("subtitles")
    if not isinstance(tracks, list):
        tracks = []
    track = next(
        (
            item
            for item in tracks
            if isinstance(item, Mapping)
            and str(item.get("language")) == selection.language
            and str(item.get("source")) == selection.source
        ),
        None,
    )
    if track is None:
        raise YouTubeServiceError(
            "subtitle_unavailable",
            "The selected subtitle/caption track is not available.",
        )

    formats = [
        str(value).strip().lower()
        for value in (track.get("formats") or [])
        if str(value).strip()
    ]
    if "srt" in formats:
        return {
            "language": selection.language,
            "source": selection.source,
            "requested_format": "srt",
            "prefer_srt": True,
        }
    if "vtt" in formats:
        return {
            "language": selection.language,
            "source": selection.source,
            "requested_format": "vtt",
            "prefer_srt": True,
        }

    fallback = str(track.get("preferred_format") or "").strip().lower()
    if not fallback and formats:
        fallback = formats[0]
    if not fallback:
        raise YouTubeServiceError(
            "subtitle_format_unavailable",
            "The selected subtitle track has no downloadable format.",
        )
    return {
        "language": selection.language,
        "source": selection.source,
        "requested_format": fallback,
        "prefer_srt": False,
    }


def reserve_available_group(
    save_directory: Path,
    title: str,
    media_extension: str,
    subtitle_extension: str | None,
) -> OutputGroup:
    for _ in range(100):
        group = select_output_group(
            save_directory,
            title,
            media_extension,
            subtitle_extension,
        )
        reserved: list[Path] = []
        try:
            for path in group.paths:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
                reserved.append(path)
            return group
        except FileExistsError:
            for path in reserved:
                path.unlink(missing_ok=True)
            continue
        except OSError:
            for path in reserved:
                path.unlink(missing_ok=True)
            raise

    raise DownloadPathError(
        "output_collision_exhausted",
        "Could not reserve a free output filename.",
    )


def cleanup_reserved_group(group: OutputGroup) -> None:
    for path in group.paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def resolve_media_source(
    info: Mapping[str, Any],
    temp_directory: Path,
    basename: str,
    extension: str,
) -> Path:
    candidates: list[Path] = []
    filepath = info.get("filepath")
    if filepath:
        candidates.append(Path(str(filepath)))
    candidates.append(temp_directory / f"{basename}.{extension}")

    for candidate in candidates:
        safe = _safe_temp_output(candidate, temp_directory)
        if safe is not None and safe.suffix.lower() == f".{extension}":
            return safe

    for candidate in temp_directory.glob(f"{basename}.*"):
        safe = _safe_temp_output(candidate, temp_directory)
        if safe is not None and safe.suffix.lower() == f".{extension}":
            return safe

    raise YouTubeServiceError(
        "output_missing",
        "Downloader completed but the final media file was not found.",
    )


def resolve_subtitle_source(
    info: Mapping[str, Any],
    temp_directory: Path,
    basename: str,
    subtitle_plan: Mapping[str, Any],
) -> Path:
    requested_format = str(subtitle_plan["requested_format"]).lower()
    language = str(subtitle_plan["language"])
    requested = info.get("requested_subtitles")
    if isinstance(requested, Mapping):
        sub = requested.get(language)
        if isinstance(sub, Mapping) and sub.get("filepath"):
            candidate = _safe_temp_output(
                Path(str(sub["filepath"])),
                temp_directory,
            )
            if candidate is not None:
                return candidate

    expected = _safe_temp_output(
        temp_directory / f"{basename}.{language}.{requested_format}",
        temp_directory,
    )
    if expected is not None:
        return expected

    for path in temp_directory.glob(f"{basename}.{language}.*"):
        candidate = _safe_temp_output(path, temp_directory)
        if candidate is not None:
            return candidate

    raise YouTubeServiceError(
        "subtitle_output_missing",
        "Downloader completed but the selected subtitle file was not found.",
    )


def _safe_temp_output(candidate: Path, temp_directory: Path) -> Path | None:
    """Return a real file only when it resolves inside the job temp directory."""
    try:
        root = temp_directory.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except OSError:
        return None

    if not resolved.is_file():
        return None
    if root not in resolved.parents:
        return None
    return resolved


def try_convert_subtitle_to_srt(
    source: Path,
    target: Path,
    ffmpeg_path: str,
    *,
    progress_callback: Callable[[DownloadProgress], None] | None = None,
) -> tuple[Path, str]:
    emit_progress(
        progress_callback,
        DownloadProgress(
            phase="post_processing",
            status="started",
            detail="Converting subtitle to SRT",
        ),
    )
    try:
        process = subprocess.run(
            [
                ffmpeg_path,
                "-nostdin",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                str(target),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        process = None

    if (
        process is not None
        and process.returncode == 0
        and target.is_file()
        and target.stat().st_size > 0
    ):
        emit_progress(
            progress_callback,
            DownloadProgress(
                phase="post_processing",
                status="finished",
                detail="Subtitle converted to SRT",
            ),
        )
        return target, "srt"

    fallback_format = source.suffix.lstrip(".").lower() or "unknown"
    emit_progress(
        progress_callback,
        DownloadProgress(
            phase="post_processing",
            status="finished",
            detail=f"SRT conversion unavailable; using {fallback_format}",
        ),
    )
    return source, fallback_format


def progress_hook(
    callback: Callable[[DownloadProgress], None] | None,
):
    def hook(data: Mapping[str, Any]) -> None:
        status = str(data.get("status") or "")
        if status not in {"downloading", "finished", "error"}:
            return

        downloaded = int_or_none(data.get("downloaded_bytes"))
        total = int_or_none(data.get("total_bytes"))
        estimated = int_or_none(data.get("total_bytes_estimate"))
        effective_total = total or estimated
        percent = None
        if downloaded is not None and effective_total and effective_total > 0:
            percent = min(100.0, max(0.0, downloaded * 100.0 / effective_total))

        emit_progress(
            callback,
            DownloadProgress(
                phase="post_processing" if status == "finished" else "downloading",
                status=status,
                percent=percent,
                downloaded_bytes=downloaded,
                total_bytes=effective_total,
                total_is_estimate=bool(not total and estimated),
                speed_bytes_per_second=float_or_none(data.get("speed")),
                eta_seconds=float_or_none(data.get("eta")),
                detail=(
                    "Download complete; preparing output"
                    if status == "finished"
                    else None
                ),
            ),
        )

    return hook


def postprocessor_hook(
    callback: Callable[[DownloadProgress], None] | None,
):
    def hook(data: Mapping[str, Any]) -> None:
        status = str(data.get("status") or "")
        if status not in {"started", "processing", "finished"}:
            return
        processor = str(data.get("postprocessor") or "post-processing")
        emit_progress(
            callback,
            DownloadProgress(
                phase="post_processing",
                status=status,
                detail=processor,
            ),
        )

    return hook


def emit_progress(
    callback: Callable[[DownloadProgress], None] | None,
    event: DownloadProgress,
) -> None:
    if callback is not None:
        callback(event)


def normalize_download_error(error: Exception) -> YouTubeServiceError:
    if isinstance(error, YouTubeServiceError):
        return error
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return YouTubeServiceError(
            "disk_full",
            "The save directory does not have enough free disk space.",
        )

    message = str(error).lower()
    if "no space left on device" in message or "disk full" in message:
        return YouTubeServiceError(
            "disk_full",
            "The save directory does not have enough free disk space.",
        )
    if (
        "requested format is not available" in message
        or "requested format not available" in message
    ):
        return YouTubeServiceError(
            "format_unavailable",
            "The selected YouTube quality/format is not currently available.",
        )
    if (
        "postprocessing" in message
        or "post-processing" in message
        or "ffmpeg" in message
        or "ffprobe" in message
        or "audio conversion failed" in message
    ):
        return YouTubeServiceError(
            "post_processing_failed",
            "FFmpeg post-processing failed.",
        )
    return normalize_downloader_error(error)


def validate_mode(value: str) -> str:
    if value not in VALID_MODES:
        raise YouTubeServiceError(
            "download_mode_invalid",
            "Download mode must be video_audio or audio_only.",
        )
    return value


def validate_quality(value: str) -> str:
    if value not in QUALITY_HEIGHTS:
        raise YouTubeServiceError(
            "quality_invalid",
            "Unsupported YouTube quality preset.",
        )
    return value


def int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None
