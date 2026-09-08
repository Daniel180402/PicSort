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


def _atom(kind: bytes, body: bytes) -> bytes:
    import struct

    return struct.pack(">I4s", 8 + len(body), kind) + body


def _fake_mp4(created_seconds_since_1904: int, version: int = 0) -> bytes:
    import struct

    if version == 1:
        mvhd_body = bytes([1, 0, 0, 0]) + struct.pack(">QQ", created_seconds_since_1904, 0) + b"\x00" * 88
    else:
        mvhd_body = bytes([0, 0, 0, 0]) + struct.pack(">II", created_seconds_since_1904, 0) + b"\x00" * 88
    ftyp = _atom(b"ftyp", b"isom\x00\x00\x02\x00isomiso2mp41")
    mdat = _atom(b"mdat", b"\x00" * 100)  # media data comes before moov, like a phone recording
    moov = _atom(b"moov", _atom(b"mvhd", mvhd_body))
    return ftyp + mdat + moov


def test_quicktime_datetime_reads_mvhd(tmp_path, monkeypatch):
    from datetime import timedelta, timezone

    monkeypatch.setattr(dates, "spotlight_datetime", lambda _p: None)
    when = datetime(2022, 8, 9, 10, 11, 12, tzinfo=timezone.utc)
    seconds = int((when - datetime(1904, 1, 1, tzinfo=timezone.utc)).total_seconds())
    expected = when.astimezone().replace(tzinfo=None)

    for version, name in ((0, "clip.mp4"), (1, "clip.mov")):
        path = tmp_path / name
        path.write_bytes(_fake_mp4(seconds, version=version))
        assert dates.quicktime_datetime(path) == expected
        assert dates.get_creation_date(path) == expected


def test_quicktime_datetime_rejects_missing_or_bogus_values(tmp_path):
    zero = tmp_path / "zero.mp4"
    zero.write_bytes(_fake_mp4(0))
    assert dates.quicktime_datetime(zero) is None

    ancient = tmp_path / "ancient.mp4"
    ancient.write_bytes(_fake_mp4(60))
    assert dates.quicktime_datetime(ancient) is None

    garbage = tmp_path / "garbage.mov"
    garbage.write_bytes(b"\x00\x00\x00\x08free" + b"junk" * 3)
    assert dates.quicktime_datetime(garbage) is None

    avi = tmp_path / "clip.avi"
    avi.write_bytes(_fake_mp4(1_000_000_000))
    assert dates.quicktime_datetime(avi) is None


def test_heic_exif_is_read(tmp_path):
    import pytest
    from PIL import Image

    import picsort

    if not picsort.HEIF_SUPPORTED:
        pytest.skip("pillow-heif not installed")
    exif = Image.Exif()
    exif.get_ifd(0x8769)[0x9003] = "2024:02:03 04:05:06"
    Image.new("RGB", (64, 64), (10, 200, 10)).save(tmp_path / "photo.heic", format="HEIF", exif=exif.tobytes())
    assert dates.exif_datetime(tmp_path / "photo.heic") == datetime(2024, 2, 3, 4, 5, 6)
