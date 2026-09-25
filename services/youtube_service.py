from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import shutil
from typing import Any, Mapping, Protocol
from urllib.parse import parse_qs, quote, urlparse


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
VIDEO_PATH_PREFIXES = {"shorts", "live", "embed", "v"}
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")

FORBIDDEN_V1_DOWNLOADER_OPTIONS = {
    "cookiefile",
    "cookiesfrombrowser",
    "username",
    "password",
    "videopassword",
    "usenetrc",
    "netrc_location",
    "proxy",
    "geo_verification_proxy",
    "geo_bypass",
    "geo_bypass_country",
    "geo_bypass_ip_block",
    "http_headers",
}


class YouTubeServiceError(RuntimeError):
    """Normalized YouTube/downloader failure exposed to application code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        access_restricted: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.access_restricted = access_restricted

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "access_restricted": self.access_restricted,
        }


@dataclass(frozen=True)
class YouTubeProxyConfig:
    enabled: bool = False
    host: str = ""
    port: int = 1080
    username: str = ""
    password: str = ""

    def proxy_url(self) -> str | None:
        if not self.enabled:
            return None

        host = self.host.strip()
        if not host:
            raise YouTubeServiceError(
                "proxy_invalid",
                "YouTube SOCKS5 proxy host is required.",
            )
        if (
            "://" in host
            or any(char.isspace() for char in host)
            or any(char in host for char in "/?#@")
        ):
            raise YouTubeServiceError(
                "proxy_invalid",
                "YouTube SOCKS5 proxy host is invalid.",
            )

        try:
            port = int(self.port)
        except (TypeError, ValueError) as exc:
            raise YouTubeServiceError(
                "proxy_invalid",
                "YouTube SOCKS5 proxy port is invalid.",
            ) from exc
        if not 1 <= port <= 65535:
            raise YouTubeServiceError(
                "proxy_invalid",
                "YouTube SOCKS5 proxy port must be between 1 and 65535.",
            )

        username = self.username.strip()
        password = self.password
        if password and not username:
            raise YouTubeServiceError(
                "proxy_invalid",
                "YouTube SOCKS5 proxy username is required when a password is set.",
            )

        host_for_url = host
        if ":" in host and not (host.startswith("[") and host.endswith("]")):
            host_for_url = f"[{host}]"

        auth = ""
        if username:
            auth = quote(username, safe="")
            if password:
                auth += ":" + quote(password, safe="")
            auth += "@"

        return f"socks5://{auth}{host_for_url}:{port}"

    def as_safe_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "host": self.host.strip() if self.enabled else "",
            "port": int(self.port) if self.enabled else None,
            "username_configured": bool(self.username.strip()) if self.enabled else False,
            "password_configured": bool(self.password) if self.enabled else False,
        }


@dataclass(frozen=True)
class FFmpegCapability:
    ffmpeg_path: str | None
    ffprobe_path: str | None

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg_path)

    @property
    def fully_available(self) -> bool:
        return bool(self.ffmpeg_path and self.ffprobe_path)

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "available": self.available,
            "fully_available": self.fully_available,
        }


class DownloaderBackend(Protocol):
    def inspect(self, url: str) -> Mapping[str, Any]:
        """Return downloader metadata for one URL without downloading media."""


class _QuietLogger:
    def debug(self, _message: str) -> None:
        pass

    def info(self, _message: str) -> None:
        pass

    def warning(self, _message: str) -> None:
        pass

    def error(self, _message: str) -> None:
        pass


class YtDlpBackend:
    """Small adapter that keeps yt-dlp details out of the UI/application layer."""

    def __init__(
        self,
        *,
        extra_options: Mapping[str, Any] | None = None,
        proxy: YouTubeProxyConfig | None = None,
    ) -> None:
        self.extra_options = dict(extra_options or {})
        _validate_v1_downloader_options(self.extra_options)
        self.proxy = proxy

    def inspect(self, url: str) -> Mapping[str, Any]:
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover - dependency is installed in CI
            raise YouTubeServiceError(
                "downloader_unavailable",
                "YouTube downloader dependency is not installed.",
            ) from exc

        options = dict(self.extra_options)
        proxy_url = self.proxy.proxy_url() if self.proxy is not None else None
        if proxy_url:
            options["proxy"] = proxy_url
        options.update(
            {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "logger": _QuietLogger(),
            }
        )

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=False)
        except Exception as exc:
            raise normalize_downloader_error(exc) from exc

        if not isinstance(info, Mapping):
            raise YouTubeServiceError(
                "metadata_unavailable",
                "YouTube metadata could not be read.",
            )
        return info


def _validate_v1_downloader_options(options: Mapping[str, Any]) -> None:
    forbidden = sorted(
        str(key)
        for key in options
        if str(key).lower() in FORBIDDEN_V1_DOWNLOADER_OPTIONS
    )
    if forbidden:
        raise YouTubeServiceError(
            "downloader_option_not_allowed",
            "Authenticated, raw proxy, custom-header, and geo-bypass downloader "
            "options are not allowed through generic downloader options. Use the "
            "validated YouTube SOCKS5 configuration for proxy access.",
            access_restricted=True,
        )


def detect_ffmpeg() -> FFmpegCapability:
    """Detect local FFmpeg/FFprobe binaries without starting a subprocess."""
    return FFmpegCapability(
        ffmpeg_path=shutil.which("ffmpeg"),
        ffprobe_path=shutil.which("ffprobe"),
    )


def validate_youtube_url(url: str) -> dict[str, str]:
    """Validate a single public-video-shaped YouTube URL without network access."""
    candidate = (url or "").strip()
    if not candidate:
        raise YouTubeServiceError("invalid_url", "YouTube URL is required.")

    try:
        parsed = urlparse(candidate)
    except ValueError as exc:
        raise YouTubeServiceError("invalid_url", "YouTube URL is invalid.") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise YouTubeServiceError(
            "invalid_url",
            "YouTube URL must use http or https.",
        )

    if parsed.username is not None or parsed.password is not None:
        raise YouTubeServiceError(
            "invalid_url",
            "YouTube URL must not contain embedded credentials.",
        )

    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise YouTubeServiceError(
            "invalid_url",
            "YouTube URL contains an invalid port.",
        ) from exc
    if explicit_port is not None:
        raise YouTubeServiceError(
            "invalid_url",
            "YouTube URL must not contain an explicit port.",
        )

    host = (parsed.hostname or "").lower().rstrip(".")
    if host not in YOUTUBE_HOSTS:
        raise YouTubeServiceError(
            "unsupported_url",
            "Only YouTube video URLs are supported in V1.",
        )

    video_id = _extract_video_id(parsed)
    if not video_id or not VIDEO_ID_RE.fullmatch(video_id):
        raise YouTubeServiceError(
            "unsupported_url",
            "V1 requires one direct YouTube video URL, not a playlist or channel URL.",
        )

    return {
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "video_id": video_id,
    }


def _extract_video_id(parsed) -> str | None:
    host = (parsed.hostname or "").lower().rstrip(".")
    path_parts = [part for part in parsed.path.split("/") if part]

    if host in {"youtu.be", "www.youtu.be"}:
        return path_parts[0] if path_parts else None

    if parsed.path.rstrip("/") == "/watch":
        values = parse_qs(parsed.query).get("v", [])
        return values[0].strip() if values else None

    if len(path_parts) >= 2 and path_parts[0].lower() in VIDEO_PATH_PREFIXES:
        return path_parts[1].strip()

    return None


def inspect_video(
    url: str,
    *,
    backend: DownloaderBackend | None = None,
    proxy: YouTubeProxyConfig | None = None,
) -> dict[str, Any]:
    """Inspect one YouTube video and return stable, UI-safe normalized metadata."""
    validated = validate_youtube_url(url)
    downloader = backend or YtDlpBackend(proxy=proxy)

    try:
        raw = downloader.inspect(validated["url"])
    except YouTubeServiceError:
        raise
    except Exception as exc:
        raise normalize_downloader_error(exc) from exc

    if raw.get("_type") in {"playlist", "multi_video"}:
        raise YouTubeServiceError(
            "unsupported_url",
            "V1 supports one YouTube video per job; playlists are not supported.",
        )

    normalized = normalize_metadata(raw)
    if not normalized["video_id"]:
        normalized["video_id"] = validated["video_id"]
    elif normalized["video_id"] != validated["video_id"]:
        raise YouTubeServiceError(
            "metadata_video_mismatch",
            "YouTube metadata does not match the requested video.",
        )
    return normalized


def normalize_metadata(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize yt-dlp-shaped metadata into the Telegram Harbor service contract."""
    formats = normalize_formats(raw.get("formats"))
    subtitles = normalize_subtitle_tracks(
        raw.get("subtitles"),
        raw.get("automatic_captions"),
    )

    title = _text(raw.get("title")) or "Untitled YouTube video"
    uploader = _text(raw.get("uploader"))
    channel = _text(raw.get("channel")) or uploader

    return {
        "video_id": _text(raw.get("id")),
        "title": title,
        "uploader": uploader,
        "channel": channel,
        "thumbnail": _thumbnail(raw),
        "duration_seconds": _integer(raw.get("duration")),
        "availability": _text(raw.get("availability")),
        "age_limit": _integer(raw.get("age_limit")),
        "is_live": bool(raw.get("is_live")),
        "was_live": bool(raw.get("was_live")),
        "live_status": _text(raw.get("live_status")),
        "has_drm": bool(raw.get("has_drm")),
        "estimated_size_bytes": (
            _integer(raw.get("filesize"))
            or _integer(raw.get("filesize_approx"))
        ),
        "formats": formats,
        "quality_presets": normalize_quality_presets(formats),
        "subtitles": subtitles,
    }


def _thumbnail(raw: Mapping[str, Any]) -> str | None:
    direct = _text(raw.get("thumbnail"))
    if direct:
        return direct

    thumbnails = raw.get("thumbnails")
    if not isinstance(thumbnails, list):
        return None

    for item in reversed(thumbnails):
        if isinstance(item, Mapping):
            url = _text(item.get("url"))
            if url:
                return url
    return None


def normalize_formats(raw_formats: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_formats, list):
        return []

    out = []
    for raw in raw_formats:
        if not isinstance(raw, Mapping):
            continue

        vcodec = _text(raw.get("vcodec"))
        acodec = _text(raw.get("acodec"))
        has_video = bool(vcodec and vcodec != "none")
        has_audio = bool(acodec and acodec != "none")
        if not has_video and not has_audio:
            continue

        exact_size = _integer(raw.get("filesize"))
        approx_size = _integer(raw.get("filesize_approx"))
        size = exact_size or approx_size

        out.append(
            {
                "format_id": _text(raw.get("format_id")),
                "ext": _text(raw.get("ext")),
                "format_note": _text(raw.get("format_note")),
                "resolution": _text(raw.get("resolution")),
                "width": _integer(raw.get("width")),
                "height": _integer(raw.get("height")),
                "fps": _number(raw.get("fps")),
                "vcodec": vcodec,
                "acodec": acodec,
                "has_video": has_video,
                "has_audio": has_audio,
                "tbr_kbps": _number(raw.get("tbr")),
                "abr_kbps": _number(raw.get("abr")),
                "vbr_kbps": _number(raw.get("vbr")),
                "size_bytes": size,
                "size_is_estimate": bool(size and not exact_size),
            }
        )

    return sorted(
        out,
        key=lambda item: (
            item["height"] or 0,
            item["fps"] or 0,
            item["tbr_kbps"] or 0,
            item["format_id"] or "",
        ),
        reverse=True,
    )


def normalize_quality_presets(
    formats: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    video_heights = [
        _integer(item.get("height"))
        for item in formats
        if item.get("has_video") and _integer(item.get("height"))
    ]

    def available_at(max_height: int) -> bool:
        return any(height <= max_height for height in video_heights)

    return [
        {
            "key": "best",
            "label": "Best available",
            "max_height": None,
            "available": bool(video_heights),
        },
        {
            "key": "max_1080p",
            "label": "Up to 1080p",
            "max_height": 1080,
            "available": available_at(1080),
        },
        {
            "key": "max_720p",
            "label": "Up to 720p",
            "max_height": 720,
            "available": available_at(720),
        },
        {
            "key": "max_480p",
            "label": "Up to 480p",
            "max_height": 480,
            "available": available_at(480),
        },
    ]


def normalize_subtitle_tracks(
    manual_subtitles: Any,
    automatic_captions: Any,
) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    tracks.extend(_subtitle_source_tracks(manual_subtitles, "manual"))
    tracks.extend(_subtitle_source_tracks(automatic_captions, "automatic"))
    return sorted(
        tracks,
        key=lambda item: (
            item["language"].lower(),
            0 if item["source"] == "manual" else 1,
        ),
    )


def _subtitle_source_tracks(raw_tracks: Any, source: str) -> list[dict[str, Any]]:
    if not isinstance(raw_tracks, Mapping):
        return []

    out = []
    for language, entries in raw_tracks.items():
        if not isinstance(entries, list):
            entries = []

        formats = []
        names = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            ext = _text(entry.get("ext"))
            if ext and ext not in formats:
                formats.append(ext)
            name = _text(entry.get("name"))
            if name and name not in names:
                names.append(name)

        preferred_format = _preferred_subtitle_format(formats)
        out.append(
            {
                "language": str(language),
                "name": names[0] if names else str(language),
                "source": source,
                "formats": formats,
                "preferred_format": preferred_format,
            }
        )
    return out


def _preferred_subtitle_format(formats: list[str]) -> str | None:
    lowered = {value.lower(): value for value in formats}
    if "srt" in lowered:
        return lowered["srt"]
    if "vtt" in lowered:
        return lowered["vtt"]
    return formats[0] if formats else None


def normalize_downloader_error(error: Exception) -> YouTubeServiceError:
    message = str(error).strip() or "YouTube operation failed."
    lowered = message.lower()

    rules = (
        (
            ("unsupported url", "no suitable extractor"),
            "unsupported_url",
            "This YouTube URL is not supported.",
            False,
        ),
        (
            ("private video", "this video is private"),
            "private_content",
            "This video is private and is outside Telegram Harbor V1.",
            True,
        ),
        (
            ("members-only", "members only", "join this channel"),
            "members_only",
            "This video requires channel membership and is outside Telegram Harbor V1.",
            True,
        ),
        (
            ("drm", "digital rights management"),
            "drm_protected",
            "This video is DRM-protected and cannot be downloaded by Telegram Harbor.",
            True,
        ),
        (
            (
                "sign in to confirm you're not a bot",
                "sign in to confirm you’re not a bot",
                "confirm you're not a bot",
                "confirm you’re not a bot",
                "this helps protect our community",
            ),
            "bot_verification_required",
            (
                "YouTube is asking this connection/IP to complete bot verification. "
                "This is not a copyright determination. If YouTube SOCKS5 is enabled, "
                "try disabling it or using another trusted proxy/IP. Authenticated "
                "cookie access is not enabled in Telegram Harbor V1."
            ),
            False,
        ),
        (
            (
                "sign in to confirm your age",
                "login required",
                "authentication required",
            ),
            "login_required",
            "This video requires authenticated access and is outside Telegram Harbor V1.",
            True,
        ),
        (
            (
                "not available in your country",
                "not available in your region",
                "geo-restricted",
                "geographic restriction",
            ),
            "geo_restricted",
            "This video is not available from the current server location.",
            True,
        ),
        (
            (
                "video unavailable",
                "this video is unavailable",
                "has been removed",
            ),
            "video_unavailable",
            "This video is unavailable.",
            False,
        ),
        (
            (
                "timed out",
                "timeout",
                "temporary failure in name resolution",
                "name or service not known",
                "connection reset",
                "network is unreachable",
            ),
            "network_error",
            "A network error occurred while contacting YouTube.",
            False,
        ),
    )

    for needles, code, friendly, restricted in rules:
        if any(needle in lowered for needle in needles):
            return YouTubeServiceError(
                code,
                friendly,
                access_restricted=restricted,
            )

    return YouTubeServiceError(
        "downloader_error",
        "YouTube operation failed unexpectedly.",
    )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None
