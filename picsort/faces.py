"""Optional: group photos by the people in them (needs face_recognition)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

try:
    import face_recognition
    from sklearn.cluster import DBSCAN

    FACE_REC_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional install
    FACE_REC_AVAILABLE = False

ProgressCallback = Callable[[int, int, str], None]
_FACE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def find_photos(folder: str | Path) -> list[Path]:
    folder = Path(folder)
    return sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in _FACE_EXTENSIONS and not p.name.startswith(".")
    )


def cluster_faces(
    folder: str | Path,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    eps: float = 0.45,
) -> dict[int, list[Path]]:
    """Return {person_id: [photos]} for every person seen at least twice."""
    if not FACE_REC_AVAILABLE:
        raise RuntimeError("face_recognition and scikit-learn are not installed")

    photos = find_photos(folder)
    encodings = []
    owners: list[Path] = []
    for index, path in enumerate(photos, start=1):
        if cancel_event and cancel_event.is_set():
            return {}
        if progress and (index % 5 == 0 or index == len(photos)):
            progress(index, len(photos), path.name)
        try:
            image = face_recognition.load_image_file(str(path))
            boxes = face_recognition.face_locations(image)
            for encoding in face_recognition.face_encodings(image, boxes):
                encodings.append(encoding)
                owners.append(path)
        except Exception:  # noqa: BLE001 - skip unreadable images
            continue

    if not encodings:
        return {}

    labels = DBSCAN(metric="euclidean", n_jobs=-1, eps=eps, min_samples=2).fit(encodings).labels_
    clusters: dict[int, list[Path]] = {}
    for label, path in zip(labels, owners):
        if label == -1:
            continue
        bucket = clusters.setdefault(int(label), [])
        if path not in bucket:
            bucket.append(path)
    return dict(sorted(clusters.items()))
