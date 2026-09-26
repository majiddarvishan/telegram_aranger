from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


_PREFERENCES_ENV = "TELEGRAM_HARBOR_PREFERENCES_FILE"


def preferences_path() -> Path:
    configured = os.getenv(_PREFERENCES_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".telegram_harbor" / "preferences.json"


def default_download_directory() -> str:
    return str(Path.home() / "Downloads")


def load_preference(key: str, default: Any = None) -> Any:
    path = preferences_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(payload, dict):
        return default
    return payload.get(key, default)


def save_preference(key: str, value: Any) -> None:
    path = preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            payload.update(existing)
    except (OSError, json.JSONDecodeError):
        pass

    payload[key] = value
    encoded = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    fd, temp_name = tempfile.mkstemp(
        prefix=".preferences-",
        suffix=".json",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.remove(temp_name)
        except FileNotFoundError:
            pass
