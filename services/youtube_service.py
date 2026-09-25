from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import os
import re
import shutil
import tempfile
from typing import Any, Iterator, Mapping, Protocol
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
MAX_YOUTUBE_COOKIE_BYTES = 1024 * 1024
_COOKIE_HEADERS = {
    "# HTTP Cookie File",
    "# Netscape HTTP Cookie File",
}
SUPPORTED_BROWSER_COOKIE_SOURCES = {
    "brave",
    "chrome",
    "chromium",
    "edge",
    "firefox",
    "opera",
    "safari",
    "vivaldi",
    "whale",
}
_BROWSER_AUTO_ORDER = (
    "chrome",
    "firefox",
    "edge",
    "brave",
    "chromium",
    "vivaldi",
    "opera",
    "safari",
    "whale",
)

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
class YouTubeAuthConfig:
    """Ephemeral YouTube auth from a local browser session or cookies.txt."""

    enabled: bool = False
    source: str = "cookies_file"  # browser | cookies_file
    cookie_data: bytes = b""
    browser: str = "auto"
    profile: str = ""

    def normalized_source(self) -> str | None:
        if not self.enabled:
            return None
        source = str(self.source or "").strip().lower()
        if source not in {"browser", "cookies_file"}:
            raise YouTubeServiceError(
                "youtube_auth_invalid",
                "YouTube authentication source is invalid.",
            )
        return source

    def resolved_browser(self) -> str | None:
        if self.normalized_source() != "browser":
            return None

        browser = str(self.browser or "auto").strip().lower()
        if browser == "auto":
            browser = detect_local_browser_cookie_source()
            if not browser:
                raise YouTubeServiceError(
                    "youtube_browser_session_unavailable",
                    "No supported local browser profile was detected on this host. "
                    "Choose a browser explicitly or use cookies.txt fallback.",
                )
        if browser not in SUPPORTED_BROWSER_COOKIE_SOURCES:
            raise YouTubeServiceError(
                "youtube_auth_invalid",
                "Selected browser is not supported for YouTube session cookies.",
            )
        return browser

    def cookies_from_browser_spec(
        self,
    ) -> tuple[str, str | None, None, None] | None:
        browser = self.resolved_browser()
        if browser is None:
            return None

        profile = str(self.profile or "").strip()
        if "\x00" in profile or len(profile) > 1024:
            raise YouTubeServiceError(
                "youtube_auth_invalid",
                "YouTube browser profile value is invalid.",
            )
        return (browser, profile or None, None, None)

    def normalized_cookie_bytes(self) -> bytes | None:
        if self.normalized_source() != "cookies_file":
            return None
        data = bytes(self.cookie_data or b"")
        if not data:
            raise YouTubeServiceError(
                "youtube_auth_invalid",
                "YouTube authentication is enabled but no cookies.txt data was provided.",
            )
        if len(data) > MAX_YOUTUBE_COOKIE_BYTES:
            raise YouTubeServiceError(
                "youtube_auth_invalid",
                "YouTube cookies.txt is too large.",
            )
        if b"\x00" in data:
            raise YouTubeServiceError(
                "youtube_auth_invalid",
                "YouTube cookies.txt contains invalid binary data.",
            )

        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise YouTubeServiceError(
                "youtube_auth_invalid",
                "YouTube cookies.txt must be UTF-8 text in Netscape format.",
            ) from exc

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        if not lines or lines[0].strip() not in _COOKIE_HEADERS:
            raise YouTubeServiceError(
                "youtube_auth_invalid",
                "YouTube cookies.txt must use Mozilla/Netscape cookie format.",
            )

        cookie_count = 0
        for raw_line in lines[1:]:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#") and not line.startswith("#HttpOnly_"):
                continue
            fields = raw_line.split("\t")
            if len(fields) != 7:
                raise YouTubeServiceError(
                    "youtube_auth_invalid",
                    "YouTube cookies.txt contains an invalid cookie row.",
                )
            domain = fields[0].strip()
            if domain.startswith("#HttpOnly_"):
                domain = domain[len("#HttpOnly_") :]
            normalized_domain = domain.lstrip(".").lower()
            if not (
                normalized_domain == "youtube.com"
                or normalized_domain.endswith(".youtube.com")
            ):
                raise YouTubeServiceError(
                    "youtube_auth_invalid",
                    "For safety, cookies.txt must contain only youtube.com cookies.",
                )
            cookie_count += 1

        if cookie_count == 0:
            raise YouTubeServiceError(
                "youtube_auth_invalid",
                "YouTube cookies.txt does not contain any YouTube cookies.",
            )

        normalized = "\n".join(lines).rstrip("\n") + "\n"
        return normalized.encode("utf-8")

    def as_safe_dict(self) -> dict[str, Any]:
        source = self.normalized_source()
        if source is None:
            return {
                "enabled": False,
                "source": None,
            }
        if source == "browser":
            return {
                "enabled": True,
                "source": "browser",
                "browser": str(self.browser or "auto").strip().lower(),
                "profile_configured": bool(str(self.profile or "").strip()),
            }

        normalized = self.normalized_cookie_bytes()
        return {
            "enabled": True,
            "source": "cookies_file",
            "format": "netscape",
            "size_bytes": len(normalized or b""),
        }


def detect_local_browser_cookie_source() -> str | None:
    """Best-effort local browser detection without reading cookie contents."""
    home = os.path.expanduser("~")
    local_app_data = os.getenv("LOCALAPPDATA", "")
    app_data = os.getenv("APPDATA", "")

    candidate_roots: dict[str, tuple[str, ...]] = {
        "chrome": (
            os.path.join(local_app_data, "Google", "Chrome", "User Data"),
            os.path.join(home, ".config", "google-chrome"),
            os.path.join(home, "Library", "Application Support", "Google", "Chrome"),
        ),
        "firefox": (
            os.path.join(app_data, "Mozilla", "Firefox"),
            os.path.join(home, ".mozilla", "firefox"),
            os.path.join(home, "Library", "Application Support", "Firefox"),
        ),
        "edge": (
            os.path.join(local_app_data, "Microsoft", "Edge", "User Data"),
            os.path.join(home, ".config", "microsoft-edge"),
            os.path.join(home, "Library", "Application Support", "Microsoft Edge"),
        ),
        "brave": (
            os.path.join(local_app_data, "BraveSoftware", "Brave-Browser", "User Data"),
            os.path.join(home, ".config", "BraveSoftware", "Brave-Browser"),
            os.path.join(home, "Library", "Application Support", "BraveSoftware", "Brave-Browser"),
        ),
        "chromium": (
            os.path.join(local_app_data, "Chromium", "User Data"),
            os.path.join(home, ".config", "chromium"),
            os.path.join(home, "Library", "Application Support", "Chromium"),
        ),
        "vivaldi": (
            os.path.join(local_app_data, "Vivaldi", "User Data"),
            os.path.join(home, ".config", "vivaldi"),
            os.path.join(home, "Library", "Application Support", "Vivaldi"),
        ),
        "opera": (
            os.path.join(app_data, "Opera Software", "Opera Stable"),
            os.path.join(home, ".config", "opera"),
            os.path.join(home, "Library", "Application Support", "com.operasoftware.Opera"),
        ),
        "safari": (
            os.path.join(home, "Library", "Cookies"),
        ),
        "whale": (
            os.path.join(local_app_data, "Naver", "Naver Whale", "User Data"),
            os.path.join(home, ".config", "naver-whale"),
        ),
    }

    for browser in _BROWSER_AUTO_ORDER:
        if any(path and os.path.exists(path) for path in candidate_roots[browser]):
            return browser
    return None


@contextmanager
def materialize_youtube_cookie_file(
    auth: YouTubeAuthConfig | None,
) -> Iterator[str | None]:
    """Materialize cookies.txt only for one operation; browser auth needs no file."""
    if (
        auth is None
        or not auth.enabled
        or auth.normalized_source() != "cookies_file"
    ):
        yield None
        return

    data = auth.normalized_cookie_bytes()
    fd, path = tempfile.mkstemp(
        prefix=".telegram-harbor-youtube-auth-",
        suffix=".txt",
    )
    try:
        try:
            os.fchmod(fd, 0o600)
        except (AttributeError, OSError):
            pass
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(data or b"")
            handle.flush()
        yield path
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


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
        auth: YouTubeAuthConfig | None = None,
    ) -> None:
        self.extra_options = dict(extra_options or {})
        _validate_v1_downloader_options(self.extra_options)
        self.proxy = proxy
        self.auth = auth

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
            browser_spec = (
                self.auth.cookies_from_browser_spec()
                if self.auth is not None
                else None
            )
            if browser_spec:
                options["cookiesfrombrowser"] = browser_spec
            with materialize_youtube_cookie_file(self.auth) as cookiefile:
                if cookiefile:
                    options["cookiefile"] = cookiefile
                with yt_dlp.YoutubeDL(options) as downloader:
                    info = downloader.extract_info(url, download=False)
        except YouTubeServiceError:
            raise
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
            "Raw authentication, raw proxy, custom-header, and geo-bypass downloader "
            "options are not allowed through generic downloader options. Use the "
            "validated YouTube auth/SOCKS5 configuration paths instead.",
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
    auth: YouTubeAuthConfig | None = None,
) -> dict[str, Any]:
    """Inspect one YouTube video and return stable, UI-safe normalized metadata."""
    validated = validate_youtube_url(url)
    downloader = backend or YtDlpBackend(proxy=proxy, auth=auth)

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
            (
                "failed to load cookies",
                "failed to decrypt with dpapi",
                "could not find chrome cookies database",
                "could not find chromium cookies database",
                "could not find firefox cookies database",
                "could not find edge cookies database",
                "could not find brave cookies database",
            ),
            "youtube_browser_session_unavailable",
            (
                "Browser session cookies could not be read on this host. "
                "Select the correct local browser/profile or use cookies.txt fallback."
            ),
            False,
        ),
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
                "This is not a copyright determination. Try another trusted IP/SOCKS5 "
                "route, or enable Telegram Harbor's authenticated YouTube session with "
                "a fresh youtube.com cookies.txt from a session you control."
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
            (
                "YouTube requires a signed-in session for this video. "
                "Enable Browser session or cookies.txt fallback and Inspect again."
            ),
            False,
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
