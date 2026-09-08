"""Small helpers that hide operating system differences."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = not (IS_MAC or IS_WINDOWS)


def open_path(path: str | Path) -> None:
    """Open a file or folder with the default application."""
    path = str(path)
    if IS_WINDOWS:
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
    elif IS_MAC:
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def reveal_in_file_manager(path: str | Path) -> None:
    """Show the file selected inside Finder / Explorer / the file manager."""
    path = Path(path)
    if IS_WINDOWS:
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif IS_MAC:
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])
