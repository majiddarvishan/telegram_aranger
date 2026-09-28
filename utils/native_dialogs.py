from __future__ import annotations

from pathlib import Path


class DirectoryPickerError(RuntimeError):
    pass


def choose_directory(initial_directory: str | None = None) -> str | None:
    """Open a native folder picker on the machine running YARA."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except (ImportError, RuntimeError) as exc:
        raise DirectoryPickerError(
            "Native folder picker is unavailable in this environment."
        ) from exc

    initial = str(initial_directory or "").strip()
    if initial:
        initial_path = Path(initial).expanduser()
        if not initial_path.exists():
            initial = str(initial_path.parent if initial_path.parent.exists() else Path.home())
    else:
        initial = str(Path.home())

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass
        selected = filedialog.askdirectory(
            parent=root,
            initialdir=initial,
            title="Choose YouTube download folder",
            mustexist=False,
        )
    except Exception as exc:
        raise DirectoryPickerError(
            "Native folder picker could not be opened. Enter the path manually."
        ) from exc
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass

    selected = str(selected or "").strip()
    return selected or None
