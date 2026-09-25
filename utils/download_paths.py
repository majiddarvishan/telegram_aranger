from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Iterable


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
_EXTENSION_RE = re.compile(r"^[A-Za-z0-9]{1,12}$")


class DownloadPathError(ValueError):
    """Normalized save-path/filename failure for the YouTube workflow."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class OutputGroup:
    directory: Path
    basename: str
    media_path: Path
    subtitle_path: Path | None = None

    @property
    def paths(self) -> tuple[Path, ...]:
        values = [self.media_path]
        if self.subtitle_path is not None:
            values.append(self.subtitle_path)
        return tuple(values)


def sanitize_youtube_title(title: str | None, *, max_length: int = 160) -> str:
    """Return a readable basename safe on common Windows/Linux filesystems."""
    if max_length < 1:
        raise ValueError("max_length must be greater than zero.")

    candidate = unicodedata.normalize("NFKC", (title or "").strip())
    candidate = _INVALID_FILENAME_CHARS.sub(" ", candidate)
    candidate = _WHITESPACE.sub(" ", candidate).strip(" .")

    if not candidate:
        candidate = "YouTube Video"

    candidate = _avoid_windows_reserved_name(candidate)
    candidate = _truncate_utf16_units(candidate, max_length).rstrip(" .")
    candidate = _avoid_windows_reserved_name(candidate)
    candidate = _truncate_utf16_units(candidate, max_length).rstrip(" .")
    return candidate or _truncate_utf16_units("YouTube Video", max_length) or "_"


def _avoid_windows_reserved_name(value: str) -> str:
    stem = value.split(".", 1)[0].upper()
    return f"_{value}" if stem in _WINDOWS_RESERVED else value


def _truncate_utf16_units(value: str, max_units: int) -> str:
    """Truncate without splitting characters that use two UTF-16 code units."""
    used = 0
    out: list[str] = []
    for char in value:
        units = len(char.encode("utf-16-le")) // 2
        if used + units > max_units:
            break
        out.append(char)
        used += units
    return "".join(out)


def validate_save_directory(
    value: str | os.PathLike[str] | None,
    *,
    allowed_roots: Iterable[str | os.PathLike[str]] = (),
    create: bool = False,
    verify_writable: bool = True,
) -> Path:
    """Resolve and validate a host filesystem directory for YouTube output."""
    raw = os.fspath(value).strip() if value is not None else ""
    if not raw:
        raise DownloadPathError(
            "save_directory_required",
            "Save directory is required.",
        )

    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise DownloadPathError(
            "save_directory_not_absolute",
            "Save directory must be an absolute path on the Telegram Harbor host.",
        )

    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise DownloadPathError(
            "save_directory_invalid",
            "Save directory could not be resolved.",
        ) from exc

    roots = _resolve_allowed_roots(allowed_roots)
    if roots and not _within_any_root(resolved, roots):
        raise DownloadPathError(
            "save_directory_not_allowed",
            "Save directory is outside the configured allowed roots.",
        )

    if not resolved.exists():
        if not create:
            raise DownloadPathError(
                "save_directory_missing",
                "Save directory does not exist.",
            )
        try:
            resolved.mkdir(parents=True, exist_ok=True)
            resolved = resolved.resolve(strict=True)
        except OSError as exc:
            raise DownloadPathError(
                "save_directory_create_failed",
                "Save directory could not be created.",
            ) from exc

    if not resolved.is_dir():
        raise DownloadPathError(
            "save_directory_not_directory",
            "Save path must point to a directory.",
        )

    if roots and not _within_any_root(resolved, roots):
        raise DownloadPathError(
            "save_directory_not_allowed",
            "Resolved save directory escapes the configured allowed roots.",
        )

    if verify_writable:
        _verify_directory_writable(resolved)

    return resolved


def select_output_group(
    save_directory: str | os.PathLike[str],
    title: str | None,
    media_extension: str,
    subtitle_extension: str | None = None,
) -> OutputGroup:
    """Choose one non-overwriting basename for media and optional subtitle."""
    directory = Path(save_directory).resolve(strict=True)
    if not directory.is_dir():
        raise DownloadPathError(
            "save_directory_not_directory",
            "Save path must point to a directory.",
        )

    base = sanitize_youtube_title(title)
    media_ext = _safe_extension(media_extension)
    subtitle_ext = (
        _safe_extension(subtitle_extension)
        if subtitle_extension is not None
        else None
    )

    for index in range(1, 10001):
        basename = base if index == 1 else f"{base} ({index})"
        media_path = directory / f"{basename}.{media_ext}"
        subtitle_path = (
            directory / f"{basename}.{subtitle_ext}"
            if subtitle_ext is not None
            else None
        )

        group = OutputGroup(
            directory=directory,
            basename=basename,
            media_path=media_path,
            subtitle_path=subtitle_path,
        )
        _assert_group_contained(group)

        if not any(path.exists() for path in group.paths):
            return group

    raise DownloadPathError(
        "output_collision_exhausted",
        "Could not find a free output filename.",
    )


def _resolve_allowed_roots(
    roots: Iterable[str | os.PathLike[str]],
) -> tuple[Path, ...]:
    resolved = []
    for value in roots:
        raw = os.fspath(value).strip()
        if not raw:
            continue

        root = Path(raw).expanduser()
        if not root.is_absolute():
            raise DownloadPathError(
                "allowed_root_invalid",
                "Configured YouTube download roots must be absolute paths.",
            )
        try:
            root = root.resolve(strict=True)
        except OSError as exc:
            raise DownloadPathError(
                "allowed_root_invalid",
                f"Configured YouTube download root does not exist: {raw}",
            ) from exc
        if not root.is_dir():
            raise DownloadPathError(
                "allowed_root_invalid",
                f"Configured YouTube download root is not a directory: {raw}",
            )
        resolved.append(root)
    return tuple(resolved)


def _within_any_root(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _verify_directory_writable(directory: Path) -> None:
    try:
        with tempfile.NamedTemporaryFile(
            dir=directory,
            prefix=".telegram-harbor-write-",
            delete=True,
        ):
            pass
    except OSError as exc:
        raise DownloadPathError(
            "save_directory_not_writable",
            "Save directory is not writable.",
        ) from exc


def _safe_extension(value: str) -> str:
    extension = (value or "").strip().lstrip(".")
    if not _EXTENSION_RE.fullmatch(extension):
        raise DownloadPathError(
            "invalid_output_extension",
            "Output extension is invalid.",
        )
    return extension.lower()


def _assert_group_contained(group: OutputGroup) -> None:
    for path in group.paths:
        if path.parent.resolve(strict=True) != group.directory:
            raise DownloadPathError(
                "output_path_escape",
                "Output path escapes the selected save directory.",
            )
