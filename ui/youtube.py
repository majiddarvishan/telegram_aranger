from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from services.youtube_download import (
    DownloadProgress,
    DownloadRequest,
    SubtitleSelection,
    download_video,
)
from services.youtube_policy import (
    GENERAL_RIGHTS_NOTICE,
    evaluate_download_policy,
)
from services.youtube_service import (
    YouTubeServiceError,
    detect_ffmpeg,
    inspect_video,
)
from utils.download_paths import DownloadPathError, validate_save_directory


WORKSPACE_TITLE = "YouTube Download"


def _format_bytes(size: int | float | None) -> str:
    if not size:
        return "Unknown"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _format_duration(seconds: int | None) -> str:
    if seconds is None or seconds < 0:
        return "Unknown"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def _quality_options(metadata: Mapping[str, Any]) -> list[tuple[str, str]]:
    presets = metadata.get("quality_presets")
    if not isinstance(presets, list):
        presets = []

    options: list[tuple[str, str]] = []
    for preset in presets:
        if not isinstance(preset, Mapping) or not preset.get("available"):
            continue
        key = str(preset.get("key") or "").strip()
        label = str(preset.get("label") or key).strip()
        if key:
            options.append((key, label))

    return options or [
        ("best", "Best available"),
        ("max_1080p", "Up to 1080p"),
        ("max_720p", "Up to 720p"),
        ("max_480p", "Up to 480p"),
    ]


def _subtitle_label(track: Mapping[str, Any]) -> str:
    language = str(track.get("language") or "unknown")
    name = str(track.get("name") or language)
    source = str(track.get("source") or "manual")
    source_label = "Manual" if source == "manual" else "Auto-generated"
    preferred = str(track.get("preferred_format") or "").upper()
    suffix = f" · {preferred}" if preferred else ""
    return f"{name} ({language}) · {source_label}{suffix}"


def _progress_text(event: DownloadProgress) -> str:
    phase = {
        "downloading": "Downloading",
        "post_processing": "Post-processing",
        "completed": "Completed",
    }.get(event.phase, event.phase.replace("_", " ").title())

    details: list[str] = []
    if event.downloaded_bytes is not None:
        if event.total_bytes:
            total_prefix = "~" if event.total_is_estimate else ""
            details.append(
                f"{_format_bytes(event.downloaded_bytes)} / "
                f"{total_prefix}{_format_bytes(event.total_bytes)}"
            )
        else:
            details.append(_format_bytes(event.downloaded_bytes))

    if event.speed_bytes_per_second:
        details.append(f"{_format_bytes(event.speed_bytes_per_second)}/s")
    if event.eta_seconds is not None:
        details.append(f"ETA {int(event.eta_seconds)}s")
    if event.detail:
        details.append(event.detail)

    return " · ".join([phase, *details])


def _render_metadata(metadata: Mapping[str, Any]) -> None:
    st.subheader(str(metadata.get("title") or "Untitled YouTube video"))

    thumbnail = metadata.get("thumbnail")
    if thumbnail:
        with st.container(key="youtube-thumbnail"):
            st.image(str(thumbnail), use_container_width=True)

    with st.container(key="youtube-metadata-metrics"):
        first, second, third, fourth = st.columns(4)
        first.metric(
            "Channel",
            str(metadata.get("channel") or metadata.get("uploader") or "Unknown"),
        )
        second.metric(
            "Duration",
            _format_duration(metadata.get("duration_seconds")),
        )
        third.metric(
            "Video ID",
            str(metadata.get("video_id") or "Unknown"),
        )
        fourth.metric(
            "Estimated size",
            _format_bytes(metadata.get("estimated_size_bytes")),
        )

    availability = str(metadata.get("availability") or "Unknown")
    st.caption(f"Availability: {availability}")

    formats = metadata.get("formats")
    if isinstance(formats, list) and formats:
        with st.expander("Available formats / quality information", expanded=False):
            rows = []
            for item in formats[:40]:
                if not isinstance(item, Mapping):
                    continue
                rows.append(
                    {
                        "Format": item.get("format_id") or "",
                        "Extension": item.get("ext") or "",
                        "Resolution": item.get("resolution") or (
                            f"{item.get('height')}p" if item.get("height") else ""
                        ),
                        "FPS": item.get("fps") or "",
                        "Video": "Yes" if item.get("has_video") else "No",
                        "Audio": "Yes" if item.get("has_audio") else "No",
                        "Size": _format_bytes(item.get("size_bytes")),
                    }
                )
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)

    tracks = metadata.get("subtitles")
    if isinstance(tracks, list) and tracks:
        with st.expander("Subtitle / caption tracks", expanded=False):
            st.dataframe(
                [
                    {
                        "Language": track.get("language") or "",
                        "Name": track.get("name") or "",
                        "Type": (
                            "Manual"
                            if track.get("source") == "manual"
                            else "Auto-generated"
                        ),
                        "Formats": ", ".join(track.get("formats") or []),
                        "Preferred": (
                            str(track.get("preferred_format") or "").upper()
                        ),
                    }
                    for track in tracks
                    if isinstance(track, Mapping)
                ],
                use_container_width=True,
                hide_index=True,
            )


def _render_restriction_state(metadata: Mapping[str, Any]):
    policy = evaluate_download_policy(metadata, acknowledged=False)

    st.info(GENERAL_RIGHTS_NOTICE)
    for warning in policy.warnings:
        st.warning(warning.message)

    if policy.blocked:
        st.error(
            policy.block_message
            or "This content is outside YouTube V1 support."
        )

    return policy


def _run_download(settings, metadata: Mapping[str, Any]) -> None:
    save_directory = st.session_state.get("youtube_save_directory", "").strip()
    create_directory = bool(st.session_state.get("youtube_create_directory", False))

    try:
        validate_save_directory(
            save_directory,
            allowed_roots=settings.youtube_download_roots,
            create=create_directory,
        )
    except DownloadPathError as exc:
        st.error(exc.message)
        return

    mode_label = st.session_state.get("youtube_mode", "Video + Audio")
    mode = "audio_only" if mode_label == "Audio only" else "video_audio"

    if mode == "audio_only":
        quality = "best"
    else:
        quality = st.session_state.get("youtube_quality_key", "best")

    subtitle = None
    if st.session_state.get("youtube_subtitles_enabled", False):
        tracks = metadata.get("subtitles") or []
        index = int(st.session_state.get("youtube_subtitle_index", 0))
        if not isinstance(tracks, list) or not tracks:
            st.error("No subtitle/caption track is available for this video.")
            return
        index = max(0, min(index, len(tracks) - 1))
        selected = tracks[index]
        subtitle = SubtitleSelection(
            language=str(selected.get("language") or ""),
            source=str(selected.get("source") or "manual"),
        )

    progress_bar = st.progress(0, text="Preparing download…")
    status = st.empty()

    def on_progress(event: DownloadProgress) -> None:
        if event.percent is not None:
            percent = max(0, min(int(event.percent), 100))
            progress_bar.progress(percent, text=_progress_text(event))
        else:
            status.caption(_progress_text(event))

    request = DownloadRequest(
        url=st.session_state.get("youtube_inspected_url", ""),
        save_directory=save_directory,
        mode=mode,
        quality=quality,
        subtitle=subtitle,
        acknowledged=bool(st.session_state.get("youtube_acknowledged", False)),
    )

    try:
        result = download_video(
            request,
            metadata,
            allowed_roots=settings.youtube_download_roots,
            progress_callback=on_progress,
        )
    except YouTubeServiceError as exc:
        progress_bar.empty()
        status.empty()
        st.error(exc.message)
        return
    except DownloadPathError as exc:
        progress_bar.empty()
        status.empty()
        st.error(exc.message)
        return
    except Exception:
        progress_bar.empty()
        status.empty()
        st.error("YouTube download failed unexpectedly.")
        return

    progress_bar.progress(100, text="Completed")
    status.empty()
    st.session_state.youtube_download_result = result.as_dict()
    st.success("Download completed.")

    st.code(result.media_path)
    if result.subtitle_path:
        st.caption(
            f"Subtitle: {result.subtitle_path} "
            f"({(result.subtitle_format or 'unknown').upper()}, "
            f"{result.subtitle_source or 'unknown'})"
        )


def render_youtube(settings) -> None:
    st.title(WORKSPACE_TITLE)
    st.caption(
        "Download one public YouTube video per job. Files are saved on the machine "
        "running Telegram Harbor. On a remote/server installation, this is the "
        "server host — not your browser device."
    )

    ffmpeg = detect_ffmpeg()
    if ffmpeg.fully_available:
        st.caption("FFmpeg / FFprobe: available")
    else:
        st.warning(
            "FFmpeg and FFprobe are required for video/audio merging and audio "
            "extraction. Install them on the machine running Telegram Harbor."
        )

    url = st.text_input(
        "YouTube URL",
        key="youtube_url",
        placeholder="https://www.youtube.com/watch?v=...",
    )

    if st.button("Inspect", key="youtube-inspect", type="primary"):
        st.session_state.youtube_metadata = None
        st.session_state.youtube_download_result = None
        st.session_state.youtube_acknowledged = False
        try:
            with st.spinner("Inspecting YouTube metadata…"):
                metadata = inspect_video(url)
        except YouTubeServiceError as exc:
            st.session_state.youtube_error = exc.as_dict()
        except Exception:
            st.session_state.youtube_error = {
                "code": "inspect_failed",
                "message": "YouTube inspection failed unexpectedly.",
                "access_restricted": False,
            }
        else:
            st.session_state.youtube_error = None
            st.session_state.youtube_metadata = metadata
            st.session_state.youtube_inspected_url = url.strip()

    error = st.session_state.get("youtube_error")
    if error:
        st.error(error.get("message") or "YouTube inspection failed.")

    metadata = st.session_state.get("youtube_metadata")
    if not isinstance(metadata, Mapping):
        st.info(
            "Inspect a public YouTube video first. No media is downloaded during "
            "the Inspect step."
        )
        return

    if st.session_state.get("youtube_inspected_url") != url.strip():
        st.warning(
            "The URL has changed since the last Inspect. Inspect the new URL before "
            "starting a download."
        )
        return

    _render_metadata(metadata)

    with st.container(key="youtube-output-controls"):
        mode_col, quality_col = st.columns(2)
        with mode_col:
            mode_label = st.radio(
                "Output",
                ("Video + Audio", "Audio only"),
                key="youtube_mode",
                horizontal=True,
            )

        quality_options = _quality_options(metadata)
        quality_map = {label: key for key, label in quality_options}
        with quality_col:
            if mode_label == "Audio only":
                st.selectbox(
                    "Quality",
                    ("Best available audio",),
                    disabled=True,
                    key="youtube_audio_quality_display",
                )
                st.session_state.youtube_quality_key = "best"
            else:
                selected_label = st.selectbox(
                    "Quality",
                    tuple(quality_map),
                    key="youtube_quality_label",
                )
                st.session_state.youtube_quality_key = quality_map[selected_label]

    tracks = metadata.get("subtitles")
    if not isinstance(tracks, list):
        tracks = []
    if not tracks and st.session_state.get("youtube_subtitles_enabled"):
        st.session_state.youtube_subtitles_enabled = False

    subtitles_enabled = st.checkbox(
        "Download one subtitle / caption track",
        key="youtube_subtitles_enabled",
        disabled=not tracks,
    )
    if not tracks:
        st.caption("No subtitle/caption tracks were reported for this video.")
    elif subtitles_enabled:
        labels = [_subtitle_label(track) for track in tracks]
        selected_label = st.selectbox(
            "Subtitle / caption",
            labels,
            key="youtube_subtitle_label",
        )
        st.session_state.youtube_subtitle_index = labels.index(selected_label)
        selected = tracks[st.session_state.youtube_subtitle_index]
        preferred = str(selected.get("preferred_format") or "original").upper()
        st.caption(
            "Preferred output: SRT. If SRT conversion is unavailable, Telegram "
            f"Harbor will report and keep the actual fallback format ({preferred})."
        )

    with st.container(key="youtube-save-controls"):
        st.text_input(
            "Save directory",
            key="youtube_save_directory",
            placeholder=(
                r"C:\Users\Majid\Downloads\TelegramHarbor"
                if Path.cwd().drive
                else "/home/majid/Downloads/telegram-harbor"
            ),
            help=(
                "Absolute path on the machine running Telegram Harbor. "
                "Remote deployments save to the server host."
            ),
        )
        st.checkbox(
            "Create the directory if it does not exist",
            key="youtube_create_directory",
        )

    if settings.youtube_download_roots:
        st.caption(
            "Hosted save-root restrictions are active. Output must stay under: "
            + ", ".join(settings.youtube_download_roots)
        )

    base_policy = _render_restriction_state(metadata)

    if base_policy.blocked:
        if st.session_state.get("youtube_acknowledged"):
            st.session_state.youtube_acknowledged = False
        acknowledged = False
    else:
        acknowledged = st.checkbox(
            "I acknowledge the rights/service notice and want to continue.",
            key="youtube_acknowledged",
        )

    policy = evaluate_download_policy(
        metadata,
        acknowledged=acknowledged,
    )

    can_start = (
        bool(st.session_state.get("youtube_save_directory", "").strip())
        and policy.can_download
        and ffmpeg.fully_available
        and st.session_state.get("youtube_inspected_url") == url.strip()
    )

    if st.button(
        "Download",
        key="youtube-download",
        type="primary",
        disabled=not can_start,
    ):
        _run_download(settings, metadata)

    result = st.session_state.get("youtube_download_result")
    if isinstance(result, Mapping) and result.get("media_path"):
        st.success("Last completed output")
        st.code(str(result["media_path"]))
        if result.get("subtitle_path"):
            st.code(str(result["subtitle_path"]))
