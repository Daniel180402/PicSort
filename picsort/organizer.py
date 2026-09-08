"""Copy or move media files into a Year/Month folder tree named by date."""

from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from picsort.dates import MEDIA_EXTENSIONS, get_creation_date
from picsort.hashing import files_identical

ProgressCallback = Callable[[int, int, str], None]
LogCallback = Callable[[str], None]


@dataclass
class SortOptions:
    source: Path
    destination: Path
    move: bool = False
    media_only: bool = True
    include_hidden: bool = False


@dataclass
class SortResult:
    total: int = 0
    processed: int = 0
    skipped_duplicates: int = 0
    errors: list[tuple[Path, str]] = field(default_factory=list)
    cancelled: bool = False

    @property
    def transferred(self) -> int:
        return self.processed - self.skipped_duplicates


def build_target_name(date: datetime, extension: str) -> tuple[Path, str]:
    """Return the relative folder (Year/MM-Month) and the file stem for a date."""
    folder = Path(date.strftime("%Y")) / date.strftime("%m-%B")
    stem = date.strftime("%Y-%m-%d_%H-%M-%S")
    return folder, stem + extension.lower()


def resolve_target(source: Path, target: Path) -> Path | None:
    """Pick a free file name next to ``target``.

    Returns None when a file with identical content already exists, so the
    caller can skip it. Otherwise returns ``target`` or ``target_1``, ``target_2`` …
    """
    candidate = target
    counter = 1
    while candidate.exists():
        if files_identical(source, candidate):
            return None
        candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
        counter += 1
    return candidate


class Organizer:
    def __init__(
        self,
        options: SortOptions,
        progress: ProgressCallback | None = None,
        log: LogCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.options = options
        self.progress = progress or (lambda done, total, msg: None)
        self.log = log or (lambda msg: None)
        self.cancel_event = cancel_event or threading.Event()

    def collect_files(self) -> list[Path]:
        source = self.options.source.resolve()
        destination = self.options.destination.resolve()
        files: list[Path] = []
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            if not self.options.include_hidden and any(part.startswith(".") for part in path.relative_to(source).parts):
                continue
            if self.options.media_only and path.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            if destination != source and destination in path.parents:
                continue  # already sorted output living inside the source tree
            files.append(path)
        return files

    def run(self) -> SortResult:
        files = self.collect_files()
        result = SortResult(total=len(files))
        self.log(f"Found {result.total} files to sort.")
        for path in files:
            if self.cancel_event.is_set():
                result.cancelled = True
                self.log("Cancelled.")
                break
            try:
                self._handle_file(path, result)
            except Exception as exc:  # noqa: BLE001 - keep going, report at the end
                result.errors.append((path, str(exc)))
                self.log(f"Error: {path.name}: {exc}")
            result.processed += 1
            self.progress(result.processed, result.total, path.name)
        return result

    def _handle_file(self, path: Path, result: SortResult) -> None:
        date = get_creation_date(path)
        folder, name = build_target_name(date, path.suffix)
        target_dir = self.options.destination / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target = resolve_target(path, target_dir / name)
        if target is None:
            result.skipped_duplicates += 1
            return
        if target.resolve() == path.resolve():
            return
        if self.options.move:
            shutil.move(str(path), str(target))
        else:
            shutil.copy2(path, target)
