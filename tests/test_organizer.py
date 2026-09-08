from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from picsort import organizer as org
from picsort.organizer import Organizer, SortOptions, build_target_name, resolve_target


@pytest.fixture(autouse=True)
def _no_spotlight(monkeypatch):
    from picsort import dates

    monkeypatch.setattr(dates, "spotlight_datetime", lambda _p: None)


def test_build_target_name():
    folder, name = build_target_name(datetime(2022, 11, 5, 14, 30, 9), ".JPG")
    assert folder == Path("2022") / "11-November"
    assert name == "2022-11-05_14-30-09.jpg"


def test_resolve_target_free_name(tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(b"one")
    target = tmp_path / "out" / "x.jpg"
    assert resolve_target(src, target) == target


def test_resolve_target_skips_identical(tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(b"same")
    target = tmp_path / "x.jpg"
    target.write_bytes(b"same")
    assert resolve_target(src, target) is None


def test_resolve_target_numbers_collisions(tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(b"new content")
    (tmp_path / "x.jpg").write_bytes(b"other")
    (tmp_path / "x_1.jpg").write_bytes(b"other2")
    assert resolve_target(src, tmp_path / "x.jpg") == tmp_path / "x_2.jpg"


def test_resolve_target_finds_identical_among_collisions(tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(b"dup")
    (tmp_path / "x.jpg").write_bytes(b"other")
    (tmp_path / "x_1.jpg").write_bytes(b"dup")
    assert resolve_target(src, tmp_path / "x.jpg") is None


def _sorted_files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def test_run_copies_into_year_month_and_skips_duplicates(tmp_path, image_factory):
    src, dst = tmp_path / "src", tmp_path / "dst"
    image_factory(src / "a" / "IMG_1.JPG", exif_datetime="2020:05:17 10:00:00")
    shutil.copy2(src / "a" / "IMG_1.JPG", src / "b" / "copy.jpg") if (src / "b").mkdir() is None else None
    image_factory(src / "IMG_2.jpg", color=(0, 0, 255), exif_datetime="2020:05:17 10:00:00")  # same second, different picture
    (src / "readme.txt").write_text("skip me")
    (src / ".hidden.jpg").write_bytes(b"x")

    progress = []
    result = Organizer(
        SortOptions(source=src, destination=dst),
        progress=lambda done, total, name: progress.append((done, total)),
    ).run()

    assert result.total == 3
    assert result.transferred == 2
    assert result.skipped_duplicates == 1
    assert result.errors == []
    assert progress[-1] == (3, 3)
    assert _sorted_files(dst) == [
        "2020/05-May/2020-05-17_10-00-00.jpg",
        "2020/05-May/2020-05-17_10-00-00_1.jpg",
    ]
    assert _sorted_files(src) == [".hidden.jpg", "IMG_2.jpg", "a/IMG_1.JPG", "b/copy.jpg", "readme.txt"]


def test_run_move_mode_removes_sources(tmp_path, image_factory):
    src, dst = tmp_path / "src", tmp_path / "dst"
    image_factory(src / "one.jpg", exif_datetime="2019:01:02 03:04:05")
    result = Organizer(SortOptions(source=src, destination=dst, move=True)).run()
    assert result.transferred == 1
    assert not (src / "one.jpg").exists()
    assert (dst / "2019" / "01-January" / "2019-01-02_03-04-05.jpg").exists()


def test_run_is_idempotent(tmp_path, image_factory):
    src, dst = tmp_path / "src", tmp_path / "dst"
    image_factory(src / "one.jpg", exif_datetime="2019:01:02 03:04:05")
    Organizer(SortOptions(source=src, destination=dst)).run()
    second = Organizer(SortOptions(source=src, destination=dst)).run()
    assert second.skipped_duplicates == 1
    assert _sorted_files(dst) == ["2019/01-January/2019-01-02_03-04-05.jpg"]


def test_destination_inside_source_is_not_rescanned(tmp_path, image_factory):
    src = tmp_path / "photos"
    dst = src / "sorted"
    image_factory(src / "one.jpg", exif_datetime="2019:01:02 03:04:05")
    Organizer(SortOptions(source=src, destination=dst)).run()
    second = Organizer(SortOptions(source=src, destination=dst))
    assert [p.name for p in second.collect_files()] == ["one.jpg"]


def test_all_files_mode_includes_other_types(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    (src / "doc.pdf").write_bytes(b"%PDF")
    files = Organizer(SortOptions(source=src, destination=dst, media_only=False)).collect_files()
    assert [p.name for p in files] == ["doc.pdf"]


def test_cancel_stops_early(tmp_path, image_factory):
    import threading

    src, dst = tmp_path / "src", tmp_path / "dst"
    for i in range(3):
        image_factory(src / f"{i}.jpg", color=(i * 40, 0, 0), exif_datetime=f"2019:01:0{i + 1} 00:00:00")
    cancel = threading.Event()
    cancel.set()
    result = Organizer(SortOptions(source=src, destination=dst), cancel_event=cancel).run()
    assert result.cancelled is True
    assert result.processed == 0


def test_errors_are_collected_not_raised(tmp_path, image_factory, monkeypatch):
    src, dst = tmp_path / "src", tmp_path / "dst"
    image_factory(src / "bad.jpg")
    monkeypatch.setattr(org, "get_creation_date", lambda _p: (_ for _ in ()).throw(OSError("boom")))
    result = Organizer(SortOptions(source=src, destination=dst)).run()
    assert result.processed == 1
    assert len(result.errors) == 1
    assert "boom" in result.errors[0][1]
