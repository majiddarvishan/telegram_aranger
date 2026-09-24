from __future__ import annotations

import mimetypes
import os
import re
import time
from pathlib import Path


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_file_name(name: str | None, fallback: str, mime_type: str | None = None) -> str:
    """Return a filesystem/browser-safe file name with a useful extension."""
    candidate = (name or "").strip()
    if candidate:
        candidate = Path(candidate).name
        candidate = _SAFE_NAME_RE.sub("_", candidate).strip("._")
    if not candidate:
        candidate = _SAFE_NAME_RE.sub("_", fallback).strip("._") or "media"

    if "." not in candidate and mime_type:
        extension = mimetypes.guess_extension(mime_type) or ""
        candidate += extension

    return candidate[:180]


def cache_path(
    cache_root: str,
    account_id: int,
    chat_id: int,
    message_id: int,
    media_type: str,
    file_name: str,
) -> Path:
    """Build a collision-resistant cache path without exposing credentials."""
    root = Path(cache_root)
    return (
        root
        / f"account_{account_id}"
        / f"chat_{chat_id}"
        / f"message_{message_id}"
        / f"{media_type}_{safe_file_name(file_name, 'media')}"
    )


def is_fresh(path: Path, ttl_hours: int) -> bool:
    if not path.is_file():
        return False
    if ttl_hours <= 0:
        return True
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds <= ttl_hours * 3600


def cleanup_cache(cache_root: str, ttl_hours: int, max_megabytes: int) -> None:
    """Remove expired files first, then oldest files until under the size limit."""
    root = Path(cache_root)
    if not root.exists():
        return

    files = [path for path in root.rglob("*") if path.is_file()]
    now = time.time()
    ttl_seconds = ttl_hours * 3600 if ttl_hours > 0 else None

    for path in files:
        try:
            if ttl_seconds is not None and now - path.stat().st_mtime > ttl_seconds:
                path.unlink(missing_ok=True)
        except OSError:
            continue

    files = [path for path in root.rglob("*") if path.is_file()]
    if max_megabytes <= 0:
        return

    max_bytes = max_megabytes * 1024 * 1024
    entries = []
    total = 0
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        total += stat.st_size
        entries.append((stat.st_mtime, stat.st_size, path))

    if total <= max_bytes:
        return

    for _, size, path in sorted(entries):
        try:
            path.unlink(missing_ok=True)
            total -= size
        except OSError:
            continue
        if total <= max_bytes:
            break


def atomic_replace_download(downloaded_path: str, final_path: Path) -> Path:
    """Move a completed Telegram download into its final cache location."""
    source = Path(downloaded_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, final_path)
    return final_path
