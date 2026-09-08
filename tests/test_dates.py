from __future__ import annotations

import os
import time
from datetime import datetime

from picsort import dates


def test_parse_exif_datetime_formats():
    assert dates._parse_exif_datetime("2023:07:15 12:34:56") == datetime(2023, 7, 15, 12, 34, 56)
    assert dates._parse_exif_datetime(b"2023:07:15 12:34:56\x00") == datetime(2023, 7, 15, 12, 34, 56)
    assert dates._parse_exif_datetime("2023-07-15 12:34:56") == datetime(2023, 7, 15, 12, 34, 56)
    assert dates._parse_exif_datetime("0000:00:00 00:00:00") is None
    assert dates._parse_exif_datetime("   ") is None
    assert dates._parse_exif_datetime(None) is None
    assert dates._parse_exif_datetime("garbage") is None


def test_exif_datetime_is_preferred(tmp_path, image_factory):
    path = image_factory(tmp_path / "shot.jpg", exif_datetime="2021:03:04 05:06:07")
    old = time.mktime((2010, 1, 1, 0, 0, 0, 0, 0, -1))
    os.utime(path, (old, old))
    assert dates.exif_datetime(path) == datetime(2021, 3, 4, 5, 6, 7)
    assert dates.get_creation_date(path) == datetime(2021, 3, 4, 5, 6, 7)


def test_filesystem_fallback_uses_earliest_timestamp(tmp_path, image_factory, monkeypatch):
    monkeypatch.setattr(dates, "spotlight_datetime", lambda _p: None)
    path = image_factory(tmp_path / "noexif.jpg")
    old = time.mktime((2012, 6, 1, 8, 0, 0, 0, 0, -1))
    os.utime(path, (old, old))
    assert dates.exif_datetime(path) is None
    assert dates.get_creation_date(path) == datetime(2012, 6, 1, 8, 0, 0)


def test_non_image_file_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(dates, "spotlight_datetime", lambda _p: None)
    path = tmp_path / "notes.txt"
    path.write_text("hello")
    assert isinstance(dates.get_creation_date(path), datetime)
