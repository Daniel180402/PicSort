"""Find out when a photo or video was taken."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image

from picsort.platform_utils import IS_MAC

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp",
    ".heic", ".heif", ".avif", ".dng", ".cr2", ".nef", ".arw", ".orf", ".raf",
}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".avi", ".mkv", ".3gp", ".mts", ".wmv"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# EXIF tag ids, see https://exiftool.org/TagNames/EXIF.html
_TAG_DATETIME_ORIGINAL = 0x9003
_TAG_DATETIME_DIGITIZED = 0x9004
_TAG_DATETIME = 0x0132
_IFD_EXIF = 0x8769


def _parse_exif_datetime(value: object) -> datetime | None:
    if isinstance(value, bytes):
        value = value.decode("ascii", "ignore")
    if not isinstance(value, str):
        return None
    value = value.strip().strip("\x00")
    if not value or value.startswith("0000"):
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M", "%Y:%m:%d"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def exif_datetime(path: Path) -> datetime | None:
    """Read the 'date taken' from EXIF metadata, or None if there is none."""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            try:
                exif_ifd = exif.get_ifd(_IFD_EXIF)
            except Exception:  # noqa: BLE001 - broken EXIF blocks are common
                exif_ifd = {}
            for tag in (_TAG_DATETIME_ORIGINAL, _TAG_DATETIME_DIGITIZED):
                parsed = _parse_exif_datetime(exif_ifd.get(tag))
                if parsed:
                    return parsed
            return _parse_exif_datetime(exif.get(_TAG_DATETIME))
    except Exception:  # noqa: BLE001 - unreadable or non-image file
        return None


def spotlight_datetime(path: Path) -> datetime | None:
    """Ask macOS Spotlight for the content creation date (macOS only)."""
    if not IS_MAC:
        return None
    try:
        result = subprocess.run(
            ["mdls", "-name", "kMDItemContentCreationDate", "-raw", str(path)],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = result.stdout.strip()
    if not output or output == "(null)":
        return None
    try:
        aware = datetime.strptime(output, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None
    return aware.astimezone().replace(tzinfo=None)


def filesystem_datetime(path: Path) -> datetime:
    """Best guess from the file system: the earlier of creation and modification time."""
    stat = os.stat(path)
    candidates = [stat.st_mtime]
    birth = getattr(stat, "st_birthtime", None)
    if birth:
        candidates.append(birth)
    return datetime.fromtimestamp(min(candidates))


def get_creation_date(path: str | Path) -> datetime:
    """Return the most trustworthy date available for a media file.

    Order: EXIF, macOS Spotlight, file system timestamps.
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        found = exif_datetime(path)
        if found:
            return found
    found = spotlight_datetime(path)
    if found:
        return found
    return filesystem_datetime(path)
