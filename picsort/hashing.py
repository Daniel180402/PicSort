"""Content hashing used to detect exact duplicate files."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def file_digest(path: str | Path) -> str:
    """Return a hex digest of the whole file content."""
    digest = hashlib.blake2b(digest_size=32)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_identical(first: str | Path, second: str | Path) -> bool:
    """True if both files have the same content. Cheap size check first."""
    if os.path.getsize(first) != os.path.getsize(second):
        return False
    return file_digest(first) == file_digest(second)
