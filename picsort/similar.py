"""Find visually similar images using perceptual hashes."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import imagehash
import numpy as np
from PIL import Image

from picsort.dates import IMAGE_EXTENSIONS

ProgressCallback = Callable[[int, int, str], None]

DEFAULT_THRESHOLD = 5
_HASHABLE_EXTENSIONS = IMAGE_EXTENSIONS - {".dng", ".cr2", ".nef", ".arw", ".orf", ".raf"}
_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


@dataclass
class SimilarImage:
    path: Path
    distance: int  # hamming distance to the first image of the group
    size: int


@dataclass
class SimilarGroup:
    images: list[SimilarImage]


def find_images(folder: str | Path) -> list[Path]:
    folder = Path(folder)
    return sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in _HASHABLE_EXTENSIONS and not p.name.startswith(".")
    )


def hash_image(path: Path) -> imagehash.ImageHash | None:
    try:
        with Image.open(path) as img:
            return imagehash.dhash(img)
    except Exception:  # noqa: BLE001 - corrupt or unsupported image
        return None


def compute_hashes(
    paths: list[Path],
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[Path, imagehash.ImageHash]:
    hashes: dict[Path, imagehash.ImageHash] = {}
    for index, path in enumerate(paths, start=1):
        if cancel_event and cancel_event.is_set():
            break
        hashed = hash_image(path)
        if hashed is not None:
            hashes[path] = hashed
        if progress and (index % 10 == 0 or index == len(paths)):
            progress(index, len(paths), path.name)
    return hashes


def _hash_matrix(hashes: list[imagehash.ImageHash]) -> np.ndarray:
    return np.stack([np.packbits(h.hash.flatten()) for h in hashes]).astype(np.uint8)


def group_similar(hashes: dict[Path, imagehash.ImageHash], threshold: int = DEFAULT_THRESHOLD) -> list[SimilarGroup]:
    """Cluster images whose hashes differ by at most ``threshold`` bits.

    Uses union-find over vectorised hamming distances, so tens of thousands of
    images are handled in seconds instead of minutes.
    """
    paths = list(hashes)
    count = len(paths)
    if count < 2:
        return []
    matrix = _hash_matrix([hashes[p] for p in paths])
    parent = list(range(count))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(count - 1):
        distances = _POPCOUNT[np.bitwise_xor(matrix[i + 1:], matrix[i])].sum(axis=1)
        for offset in np.flatnonzero(distances <= threshold):
            a, b = find(i), find(i + 1 + int(offset))
            if a != b:
                parent[b] = a

    members: dict[int, list[int]] = {}
    for i in range(count):
        members.setdefault(find(i), []).append(i)

    groups: list[SimilarGroup] = []
    for indices in members.values():
        if len(indices) < 2:
            continue
        first = matrix[indices[0]]
        images = [
            SimilarImage(
                path=paths[i],
                distance=int(_POPCOUNT[np.bitwise_xor(matrix[i], first)].sum()),
                size=paths[i].stat().st_size,
            )
            for i in indices
        ]
        groups.append(SimilarGroup(images=images))
    groups.sort(key=lambda g: (-len(g.images), str(g.images[0].path)))
    return groups


def scan_folder(
    folder: str | Path,
    threshold: int = DEFAULT_THRESHOLD,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> list[SimilarGroup]:
    paths = find_images(folder)
    hashes = compute_hashes(paths, progress, cancel_event)
    if cancel_event and cancel_event.is_set():
        return []
    return group_similar(hashes, threshold)
