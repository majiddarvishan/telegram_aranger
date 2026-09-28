from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from services.youtube_download import (
    DownloadProgress,
    DownloadRequest,
    SubtitleDownloadRequest,
    SubtitleSelection,
    download_subtitle,
)
from services.youtube_jobs import YouTubeDownloadJob, start_youtube_download_job
from services.youtube_policy import (
    GENERAL_RIGHTS_NOTICE,
    evaluate_download_policy,
)
from services.youtube_service import (
    YouTubeAuthConfig,
    YouTubeProxyConfig,
    YouTubeServiceError,
    detect_ffmpeg,
    inspect_video,
)
from utils.download_paths import DownloadPathError, validate_save_directory
from utils.native_dialogs import DirectoryPickerError, choose_directory
from utils.preferences import save_preference


WORKSPACE_TITLE = "YouTube Download"


def _remember_youtube_save_directory() -> None:
    value = str(st.session_state.get("youtube_save_directory", "") or "").strip()
    if value:
        save_preference("youtube_save_directory", value)


def _apply_pending_youtube_save_directory() -> None:
    selected = st.session_state.get("youtube_pending_save_directory")
    if not selected:
        return
    st.session_state.youtube_save_directory = str(selected)
    st.session_state.youtube_pending_save_directory = None


def _browse_youtube_save_directory() -> None:
    current = str(
        st.session_state.get("youtube_save_directory", "") or ""
    ).strip()
    selected = choose_directory(current)
    if selected:
        st.session_state.youtube_pending_save_directory = selected
        save_preference("youtube_save_directory", selected)


def _invalidate_youtube_inspection() -> None:
    active_job = st.session_state.get("youtube_download_job")
    if _job_is_active(active_job):
        active_job.request_cancel()
    st.session_state.youtube_metadata = None
    st.session_state.youtube_error = None
    st.session_state.youtube_download_result = None
    st.session_state.youtube_acknowledged = False
    st.session_state.youtube_inspected_url = ""


def _youtube_auth_config() -> YouTubeAuthConfig | None:
    if not st.session_state.get("youtube_use_auth", False):
        return None

    source = st.session_state.get(
        "youtube_auth_source",
        "Browser session",
    )
    if source == "Browser session":
        return YouTubeAuthConfig(
            enabled=True,
            source="browser",
            browser=str(
                st.session_state.get(
                    "youtube_auth_browser",
                    "Auto",
                )
            ).strip().lower(),
            profile=str(
                st.session_state.get(
                    "youtube_auth_profile",
                    "",
                )
            ).strip(),
        )

    uploaded = st.session_state.get("youtube_cookie_upload")
    cookie_data = uploaded.getvalue() if uploaded is not None else b""
    return YouTubeAuthConfig(
        enabled=True,
        source="cookies_file",
        cookie_data=cookie_data,
    )


def _render_youtube_auth_settings() -> None:
    with st.expander("YouTube sign-in", expanded=False):
        st.checkbox(
            "Use authenticated YouTube session",
            key="youtube_use_auth",
            on_change=_invalidate_youtube_inspection,
        )
        st.caption(
            "No Google username/password is requested. For local installs, "
            "YARA can use the signed-in session from a browser on "
            "the same host. cookies.txt remains a fallback for Docker/servers."
        )

        if not st.session_state.get("youtube_use_auth", False):
            return

        st.warning(
            "Browser/account cookies are sensitive and YouTube may rotate them. "
            "Use authentication only when needed. YARA does not store "
            "the cookie values in its database or validation reports."
        )

        source = st.selectbox(
            "Authentication source",
            ("Browser session", "cookies.txt fallback"),
            key="youtube_auth_source",
            on_change=_invalidate_youtube_inspection,
        )

        if source == "Browser session":
            st.selectbox(
                "Browser",
                (
                    "Auto",
                    "Chrome",
                    "Firefox",
                    "Edge",
                    "Brave",
                    "Chromium",
                    "Vivaldi",
                    "Opera",
                    "Safari",
                    "Whale",
                ),
                key="youtube_auth_browser",
                on_change=_invalidate_youtube_inspection,
                help=(
                    "Auto checks standard local browser-profile locations without "
                    "reading cookie contents. On Windows, Firefox is preferred because "
                    "modern Chromium browsers may use App-Bound cookie encryption that "
                    "yt-dlp cannot decrypt directly. The selected browser must exist on "
                    "the same machine/user account that runs YARA."
                ),
            )
            st.text_input(
                "Browser profile (optional)",
                key="youtube_auth_profile",
                on_change=_invalidate_youtube_inspection,
                help=(
                    "Leave empty to use yt-dlp's default/most recently accessed "
                    "profile. You can provide a profile name or path when needed."
                ),
            )
            st.caption(
                "Local installs: this can reuse your existing signed-in browser "
                "session without exporting cookies. Remote/Docker deployments "
                "cannot read cookies from a browser running on your own PC."
            )
            st.caption(
                "Windows note: Firefox is the preferred Browser Session source. "
                "Recent Chrome/Edge/Brave versions can use App-Bound cookie "
                "encryption that prevents direct yt-dlp decryption."
            )
        else:
            st.file_uploader(
                "YouTube cookies.txt",
                type=("txt",),
                key="youtube_cookie_upload",
                on_change=_invalidate_youtube_inspection,
                help=(
                    "Fallback for remote/Docker installs. Use Mozilla/Netscape "
                    "cookies.txt exported for youtube.com only. The upload stays "
                    "in this Streamlit session and is materialized temporarily "
                    "only while Inspect/Download is running."
                ),
            )
            uploaded = st.session_state.get("youtube_cookie_upload")
            if uploaded is None:
                st.info(
                    "Upload a youtube.com-only cookies.txt file before Inspect."
                )
            else:
                st.caption(
                    "Authenticated cookies.txt loaded for this Streamlit session."
                )


def _youtube_proxy_config() -> YouTubeProxyConfig | None:
    if not st.session_state.get("use_proxy", False):
        return None
    return YouTubeProxyConfig(
        enabled=True,
        host=str(st.session_state.get("proxy_host", "")).strip(),
        port=int(st.session_state.get("proxy_port", 1080)),
        username=str(st.session_state.get("proxy_user", "")),
        password=str(st.session_state.get("proxy_pass", "")),
    )


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
            st.image(str(thumbnail), width="stretch")

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




def _render_restriction_state(metadata: Mapping[str, Any]):
    policy = evaluate_download_policy(
        metadata,
        acknowledged=False,
        authenticated_session=bool(
            st.session_state.get("youtube_use_auth", False)
        ),
    )

    for warning in policy.warnings:
        st.warning(warning.message)

    if policy.blocked:
        st.error(
            policy.block_message
            or "This content is outside YouTube V1 support."
        )

    return policy


def _build_download_request(
    settings,
    metadata: Mapping[str, Any],
    *,
    mode_override: str | None = None,
    format_id: str | None = None,
    include_ui_subtitle: bool = True,
) -> DownloadRequest:
    save_directory = str(
        st.session_state.get("youtube_save_directory", "") or ""
    ).strip()
    create_directory = bool(
        st.session_state.get("youtube_create_directory", False)
    )

    validate_save_directory(
        save_directory,
        allowed_roots=settings.youtube_download_roots,
        create=create_directory,
    )

    mode_label = st.session_state.get("youtube_mode", "Video + Audio")
    mode = mode_override or (
        "audio_only" if mode_label == "Audio only" else "video_audio"
    )
    quality = (
        "best"
        if mode == "audio_only" or format_id
        else st.session_state.get("youtube_quality_key", "best")
    )

    subtitle = None
    if (
        include_ui_subtitle
        and st.session_state.get("youtube_subtitles_enabled", False)
    ):
        tracks = metadata.get("subtitles") or []
        index = int(st.session_state.get("youtube_subtitle_index", 0))
        if not isinstance(tracks, list) or not tracks:
            raise YouTubeServiceError(
                "subtitle_unavailable",
                "No subtitle/caption track is available for this video.",
            )
        index = max(0, min(index, len(tracks) - 1))
        selected = tracks[index]
        subtitle = SubtitleSelection(
            language=str(selected.get("language") or ""),
            source=str(selected.get("source") or "manual"),
        )

    return DownloadRequest(
        url=st.session_state.get("youtube_inspected_url", ""),
        save_directory=save_directory,
        mode=mode,
        quality=quality,
        subtitle=subtitle,
        acknowledged=bool(
            st.session_state.get("youtube_acknowledged", False)
        ),
        proxy=_youtube_proxy_config(),
        auth=_youtube_auth_config(),
        format_id=format_id,
    )


def _selected_quick_subtitle(
    metadata: Mapping[str, Any],
    selected_label: str | None,
) -> SubtitleSelection:
    tracks = metadata.get("subtitles")
    if not isinstance(tracks, list) or not tracks:
        raise YouTubeServiceError(
            "subtitle_unavailable",
            "No subtitle/caption track is available for this video.",
        )

    labels = [_subtitle_label(track) for track in tracks]
    label = str(selected_label or "").strip()
    try:
        index = labels.index(label)
    except ValueError:
        index = 0
    selected = tracks[index]
    return SubtitleSelection(
        language=str(selected.get("language") or ""),
        source=str(selected.get("source") or "manual"),
    )


def _start_format_download(
    settings,
    metadata: Mapping[str, Any],
    *,
    format_id: str,
    action: str,
    subtitle_label: str | None = None,
) -> None:
    if action == "subtitle":
        save_directory = str(
            st.session_state.get("youtube_save_directory", "") or ""
        ).strip()
        validate_save_directory(
            save_directory,
            allowed_roots=settings.youtube_download_roots,
            create=bool(
                st.session_state.get("youtube_create_directory", False)
            ),
        )
        request = SubtitleDownloadRequest(
            url=st.session_state.get("youtube_inspected_url", ""),
            save_directory=save_directory,
            subtitle=_selected_quick_subtitle(
                metadata,
                subtitle_label,
            ),
            acknowledged=bool(
                st.session_state.get("youtube_acknowledged", False)
            ),
            proxy=_youtube_proxy_config(),
            auth=_youtube_auth_config(),
        )
        runner = download_subtitle
    else:
        mode = "audio_only" if action == "audio" else "video_audio"
        request = _build_download_request(
            settings,
            metadata,
            mode_override=mode,
            format_id=format_id,
            include_ui_subtitle=False,
        )
        runner = None

    st.session_state.youtube_download_result = None
    kwargs = {
        "allowed_roots": settings.youtube_download_roots,
    }
    if runner is not None:
        kwargs["runner"] = runner
    st.session_state.youtube_download_job = start_youtube_download_job(
        request,
        metadata,
        **kwargs,
    )


def _render_format_downloads(
    settings,
    metadata: Mapping[str, Any],
    *,
    can_start: bool,
) -> None:
    formats = metadata.get("formats")
    if not isinstance(formats, list) or not formats:
        st.caption("No downloadable YouTube formats were reported.")
        return

    tracks = metadata.get("subtitles")
    if not isinstance(tracks, list):
        tracks = []

    video_count = sum(
        1
        for item in formats
        if isinstance(item, Mapping) and item.get("has_video")
    )
    audio_count = sum(
        1
        for item in formats
        if isinstance(item, Mapping) and item.get("has_audio")
    )

    with st.expander(
        "Available formats / quality information",
        expanded=True,
    ):
        st.caption(
            f"{video_count} video format(s) · "
            f"{audio_count} audio-capable format(s) · "
            f"{len(formats)} total"
        )

        if not tracks:
            st.caption("No subtitle/caption track is available.")

        current_job = st.session_state.get("youtube_download_job")
        busy = _job_is_active(current_job)

        # Keep the header outside the scrollable rows container so it
        # remains visible while the user scrolls through all formats.
        header = st.columns(
            [1.0, 0.8, 1.2, 0.6, 0.8, 0.8, 1.0, 1.1]
        )
        for col, label in zip(
            header,
            (
                "Format",
                "Ext",
                "Resolution",
                "FPS",
                "Video",
                "Audio",
                "Size",
                "Download",
            ),
        ):
            col.markdown(f"**{label}**")

        table = st.container(height=560)
        with table:
            for index, item in enumerate(formats):
                if not isinstance(item, Mapping):
                    continue

                format_id = str(item.get("format_id") or "").strip()
                if not format_id:
                    continue

                row = st.columns(
                    [1.0, 0.8, 1.2, 0.6, 0.8, 0.8, 1.0, 1.1]
                )
                row[0].write(format_id)
                row[1].write(str(item.get("ext") or ""))
                row[2].write(
                    str(
                        item.get("resolution")
                        or (
                            f"{item.get('height')}p"
                            if item.get("height")
                            else "audio only"
                        )
                    )
                )
                row[3].write(str(item.get("fps") or ""))
                has_video = bool(item.get("has_video"))
                has_audio = bool(item.get("has_audio"))
                row[4].write("Yes" if has_video else "No")
                row[5].write("Yes" if has_audio else "No")
                row[6].write(_format_bytes(item.get("size_bytes")))

                subtitle_label = None
                with row[7].popover(
                    "Download",
                    width="stretch",
                ):
                    video_clicked = st.button(
                        "Video + Audio",
                        key=f"youtube-format-video-{index}-{format_id}",
                        disabled=not can_start or busy or not has_video,
                        width="stretch",
                        help=(
                            "Use this exact video format and merge the best "
                            "available audio when the row has no audio."
                        ),
                    )
                    audio_clicked = st.button(
                        "Audio",
                        key=f"youtube-format-audio-{index}-{format_id}",
                        disabled=not can_start or busy or not has_audio,
                        width="stretch",
                        help=(
                            "Use this exact audio-capable format and extract "
                            "an MP3 output."
                        ),
                    )

                    if tracks:
                        labels = [_subtitle_label(track) for track in tracks]
                        subtitle_label = st.selectbox(
                            "Subtitle language",
                            labels,
                            key=(
                                f"youtube-format-subtitle-language-"
                                f"{index}-{format_id}"
                            ),
                        )
                    subtitle_clicked = st.button(
                        "Subtitle",
                        key=f"youtube-format-subtitle-{index}-{format_id}",
                        disabled=not can_start or busy or not tracks,
                        width="stretch",
                        help=(
                            "Download only the subtitle/caption language "
                            "selected above."
                        ),
                    )

                action = (
                    "video_audio"
                    if video_clicked
                    else "audio"
                    if audio_clicked
                    else "subtitle"
                    if subtitle_clicked
                    else None
                )
                if action is not None:
                    try:
                        _start_format_download(
                            settings,
                            metadata,
                            format_id=format_id,
                            action=action,
                            subtitle_label=subtitle_label,
                        )
                    except (YouTubeServiceError, DownloadPathError) as exc:
                        st.error(exc.message)
                    else:
                        st.rerun()


def _start_download(settings, metadata: Mapping[str, Any]) -> None:
    request = _build_download_request(settings, metadata)
    st.session_state.youtube_download_result = None
    st.session_state.youtube_download_job = start_youtube_download_job(
        request,
        metadata,
        allowed_roots=settings.youtube_download_roots,
    )


def _job_is_active(job: Any) -> bool:
    return (
        isinstance(job, YouTubeDownloadJob)
        and job.snapshot()["status"] in {"running", "cancelling"}
    )


@st.fragment(run_every="500ms")
def _render_active_download_job() -> None:
    job = st.session_state.get("youtube_download_job")
    if not isinstance(job, YouTubeDownloadJob):
        return

    snapshot = job.snapshot()
    status = snapshot["status"]
    if status not in {"running", "cancelling"}:
        st.rerun()
        return

    progress = snapshot.get("progress")
    if isinstance(progress, DownloadProgress):
        percent = (
            max(0, min(int(progress.percent), 100))
            if progress.percent is not None
            else 0
        )
        st.progress(percent, text=_progress_text(progress))
    else:
        st.progress(0, text="Preparing download…")

    if status == "cancelling":
        st.caption("Cancelling download…")
    if st.button(
        "Cancel download",
        key="youtube-cancel-download",
        disabled=status == "cancelling",
        type="secondary",
    ):
        job.request_cancel()


def _render_download_job_status() -> None:
    job = st.session_state.get("youtube_download_job")
    if not isinstance(job, YouTubeDownloadJob):
        return

    snapshot = job.snapshot()
    status = snapshot["status"]
    if status in {"running", "cancelling"}:
        _render_active_download_job()
        return

    if status == "cancelled":
        st.info("YouTube download cancelled.")
        return

    if status == "failed":
        error = snapshot.get("error") or {}
        st.error(error.get("message") or "YouTube download failed.")
        return

    result = snapshot.get("result")
    if status == "completed" and result is not None:
        st.session_state.youtube_download_result = result.as_dict()
        st.success("Download completed.")


def render_youtube(settings) -> None:
    _apply_pending_youtube_save_directory()
    st.title(WORKSPACE_TITLE)
    st.caption(
        "Download one public YouTube video per job. Files are saved on the machine "
        "running YARA. On a remote/server installation, this is the "
        "server host — not your browser device."
    )
    st.info(GENERAL_RIGHTS_NOTICE)

    ffmpeg = detect_ffmpeg()
    if ffmpeg.fully_available:
        st.caption("FFmpeg / FFprobe: available")
    else:
        st.warning(
            "FFmpeg and FFprobe are required for video/audio merging and audio "
            "extraction. Install them on the machine running YARA."
        )

    _render_youtube_auth_settings()

    url = st.text_input(
        "YouTube URL",
        key="youtube_url",
        placeholder="https://www.youtube.com/watch?v=...",
        on_change=_invalidate_youtube_inspection,
    )

    inspect_feedback = st.empty()

    if st.button("Inspect", key="youtube-inspect", type="primary"):
        st.session_state.youtube_error = None
        st.session_state.youtube_metadata = None
        st.session_state.youtube_download_result = None
        st.session_state.youtube_acknowledged = False
        st.session_state.youtube_inspected_url = ""

        try:
            with inspect_feedback.container():
                with st.spinner("Inspecting YouTube metadata…"):
                    metadata = inspect_video(
                        url,
                        proxy=_youtube_proxy_config(),
                        auth=_youtube_auth_config(),
                    )
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

        inspect_feedback.empty()

    error = st.session_state.get("youtube_error")
    metadata = st.session_state.get("youtube_metadata")

    if error:
        inspect_feedback.error(
            error.get("message") or "YouTube inspection failed."
        )
    elif not isinstance(metadata, Mapping):
        inspect_feedback.info(
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

    with st.container(key="youtube-save-controls"):
        path_col, browse_col = st.columns([5, 1])
        with path_col:
            st.text_input(
                "Save directory",
                key="youtube_save_directory",
                on_change=_remember_youtube_save_directory,
                help=(
                    "Absolute path on the machine running YARA. "
                    "The default is your Downloads folder and the last selected "
                    "path is remembered across restarts."
                ),
            )
        with browse_col:
            st.write("")
            st.write("")
            if st.button(
                "Browse…",
                key="youtube-browse-save-directory",
                width="stretch",
            ):
                try:
                    _browse_youtube_save_directory()
                except DirectoryPickerError as exc:
                    st.warning(str(exc))
                else:
                    st.rerun()

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
        authenticated_session=bool(
            st.session_state.get("youtube_use_auth", False)
        ),
    )

    save_directory_ready = bool(
        st.session_state.get("youtube_save_directory", "").strip()
    )
    inspected_url_ready = (
        st.session_state.get("youtube_inspected_url") == url.strip()
    )
    can_start = (
        save_directory_ready
        and policy.can_download
        and ffmpeg.fully_available
        and inspected_url_ready
    )

    if not can_start:
        reasons = []
        if not save_directory_ready:
            reasons.append("set a save directory")
        if not policy.can_download:
            reasons.append("acknowledge the rights/service notice")
        if not ffmpeg.fully_available:
            reasons.append("make FFmpeg and FFprobe available to the Streamlit process")
        if not inspected_url_ready:
            reasons.append("Inspect the current URL again")
        st.caption("Download unavailable: " + "; ".join(reasons) + ".")

    _render_format_downloads(
        settings,
        metadata,
        can_start=can_start,
    )

    _render_download_job_status()

    result = st.session_state.get("youtube_download_result")
    if isinstance(result, Mapping) and (
        result.get("media_path") or result.get("subtitle_path")
    ):
        st.success("Last completed output")
        if result.get("media_path"):
            st.code(str(result["media_path"]))
        if result.get("subtitle_path"):
            st.code(str(result["subtitle_path"]))
            st.caption(
                "Subtitle: "
                f"{result.get('subtitle_language') or 'unknown'} · "
                f"{str(result.get('subtitle_format') or 'unknown').upper()} · "
                f"{result.get('subtitle_source') or 'unknown'}"
            )
