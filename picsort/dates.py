"""Find out when a photo or video was taken."""

from __future__ import annotations

import os
import struct
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from picsort.platform_utils import IS_MAC

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp",
    ".heic", ".heif", ".avif", ".dng", ".cr2", ".nef", ".arw", ".orf", ".raf",
}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".avi", ".mkv", ".3gp", ".mts", ".wmv"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
_QUICKTIME_EXTENSIONS = {".mp4", ".m4v", ".mov", ".3gp"}
_SPOTLIGHT_EXTENSIONS = VIDEO_EXTENSIONS - _QUICKTIME_EXTENSIONS
_QUICKTIME_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)

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


def _iter_atoms(handle, start: int, end: int):
    """Yield (type, body_start, body_end) for each ISO-BMFF/QuickTime atom in a range."""
    position = start
    while position + 8 <= end:
        handle.seek(position)
        header = handle.read(8)
        if len(header) < 8:
            return
        size, kind = struct.unpack(">I4s", header)
        header_length = 8
        if size == 1:  # 64-bit size follows
            size = struct.unpack(">Q", handle.read(8))[0]
            header_length = 16
        elif size == 0:  # atom runs to the end of the file
            size = end - position
        if size < header_length:
            return
        yield kind, position + header_length, position + size
        position += size


def quicktime_datetime(path: Path) -> datetime | None:
    """Read the creation time stored in MP4/MOV/M4V files (the 'mvhd' atom)."""
    if path.suffix.lower() not in _QUICKTIME_EXTENSIONS:
        return None
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            file_end = handle.tell()
            for kind, body_start, body_end in _iter_atoms(handle, 0, file_end):
                if kind != b"moov":
                    continue
                for child, child_start, _child_end in _iter_atoms(handle, body_start, body_end):
                    if child != b"mvhd":
                        continue
                    handle.seek(child_start)
                    version = handle.read(4)[0]
                    raw = handle.read(8 if version == 1 else 4)
                    created = struct.unpack(">Q" if version == 1 else ">I", raw)[0]
                    if created == 0:
                        return None
                    utc = _QUICKTIME_EPOCH + timedelta(seconds=created)
                    if utc.year < 1980 or utc > datetime.now(timezone.utc) + timedelta(days=1):
                        return None
                    return utc.astimezone().replace(tzinfo=None)
    except (OSError, struct.error, IndexError, OverflowError):
        return None
    return None


def spotlight_datetime(path: Path) -> datetime | None:
    """Ask macOS Spotlight for the content creation date (macOS only).

    Spawning ``mdls`` costs about 30 ms per file, so this is only used for
    video formats PicSort cannot read itself.
    """
    if not IS_MAC or path.suffix.lower() not in _SPOTLIGHT_EXTENSIONS:
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

    Order: EXIF (photos), embedded creation time (videos), macOS Spotlight
    (other videos), file system timestamps.
    """
    path = Path(path)
    ext = path.suffix.lower()
    found = None
    if ext in IMAGE_EXTENSIONS:
        found = exif_datetime(path)
    elif ext in VIDEO_EXTENSIONS:
        found = quicktime_datetime(path)
    if found:
        return found
    found = spotlight_datetime(path)
    if found:
        return found
    return filesystem_datetime(path)
