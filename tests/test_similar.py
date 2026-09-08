from __future__ import annotations

import threading

from PIL import Image, ImageDraw

import pytest

from picsort import similar
from picsort.similar import HashCache, compute_hashes, find_images, group_similar, scan_folder


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(similar, "user_cache_dir", lambda *_a: tmp_path / "cache")


def _photo(path, seed: int, size=(160, 120)):
    """A gradient-ish image so dhash is meaningful (flat colours all hash to zero)."""
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    for x in range(size[0]):
        draw.line([(x, 0), (x, size[1])], fill=((x * seed) % 256, (x * 3 + seed * 17) % 256, (seed * 29 + x // 2) % 256))
    draw.ellipse([20 + seed * 3, 20, 80 + seed * 3, 80], fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return img


def test_groups_near_duplicates_but_not_different_images(tmp_path):
    original = _photo(tmp_path / "a" / "orig.jpg", seed=1)
    original.resize((80, 60)).save(tmp_path / "small.png")  # resized copy
    original.save(tmp_path / "recompressed.jpg", quality=40)  # re-encoded copy
    _photo(tmp_path / "other.jpg", seed=9)
    (tmp_path / "notes.txt").write_text("not an image")
    (tmp_path / "broken.jpg").write_bytes(b"definitely not a jpeg")

    groups = scan_folder(tmp_path, threshold=5)

    assert len(groups) == 1
    names = sorted(img.path.name for img in groups[0].images)
    assert names == ["orig.jpg", "recompressed.jpg", "small.png"]
    assert groups[0].images[0].distance == 0
    assert all(img.distance <= 5 for img in groups[0].images)


def test_threshold_zero_only_matches_identical(tmp_path):
    from PIL import ImageDraw

    original = _photo(tmp_path / "orig.png", seed=2)
    original.save(tmp_path / "exact.png")
    altered = original.copy()
    ImageDraw.Draw(altered).rectangle([0, 0, 80, 120], fill=(0, 0, 0))  # black out the left half
    altered.save(tmp_path / "altered.png")

    hashes = compute_hashes(find_images(tmp_path))
    assert hashes[tmp_path / "altered.png"] - hashes[tmp_path / "orig.png"] > 0

    groups = group_similar(hashes, threshold=0)
    assert len(groups) == 1
    assert sorted(i.path.name for i in groups[0].images) == ["exact.png", "orig.png"]
    assert all(i.distance == 0 for i in groups[0].images)


def test_no_groups_for_single_or_unrelated_images(tmp_path):
    _photo(tmp_path / "one.jpg", seed=3)
    assert scan_folder(tmp_path) == []
    _photo(tmp_path / "two.jpg", seed=11)
    assert scan_folder(tmp_path, threshold=2) == []


def test_progress_and_cancel(tmp_path):
    for i in range(12):
        _photo(tmp_path / f"{i}.jpg", seed=i + 1)
    calls = []
    compute_hashes(find_images(tmp_path), progress=lambda d, t, n: calls.append((d, t)))
    assert calls[-1] == (12, 12)

    cancel = threading.Event()
    cancel.set()
    assert scan_folder(tmp_path, cancel_event=cancel) == []


def test_cache_skips_rehashing_until_file_changes(tmp_path, monkeypatch):
    for i in range(4):
        _photo(tmp_path / f"{i}.jpg", seed=i + 1)
    calls = []
    real_hash = similar.hash_image
    monkeypatch.setattr(similar, "hash_image", lambda p: calls.append(p) or real_hash(p))
    cache_file = tmp_path / "cache" / "hashes.json"

    first = compute_hashes(find_images(tmp_path), cache=HashCache(cache_file).load())
    assert len(calls) == 4
    assert cache_file.exists()

    calls.clear()
    cache = HashCache(cache_file).load()
    second = compute_hashes(find_images(tmp_path), cache=cache)
    assert calls == []
    assert cache.hits == 4
    assert second == first

    import os
    import time

    changed = tmp_path / "2.jpg"
    _photo(changed, seed=42)
    os.utime(changed, (time.time() + 5, time.time() + 5))
    calls.clear()
    compute_hashes(find_images(tmp_path), cache=HashCache(cache_file).load())
    assert calls == [changed]


def test_corrupt_cache_file_is_ignored(tmp_path):
    cache_file = tmp_path / "cache" / "hashes.json"
    cache_file.parent.mkdir()
    cache_file.write_text("{not json")
    _photo(tmp_path / "a.jpg", seed=1)
    hashes = compute_hashes(find_images(tmp_path), cache=HashCache(cache_file).load())
    assert len(hashes) == 1
    assert cache_file.read_text().startswith("{")


def test_scan_folder_uses_default_cache_location(tmp_path):
    _photo(tmp_path / "a.jpg", seed=1)
    scan_folder(tmp_path)
    assert (tmp_path / "cache" / "image_hashes.json").exists()
    scan_folder(tmp_path, use_cache=False)
