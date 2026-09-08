from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


def make_image(path: Path, color=(200, 30, 30), size=(64, 48), exif_datetime: str | None = None) -> Path:
    """Create a small JPEG, optionally with an EXIF DateTimeOriginal tag."""
    img = Image.new("RGB", size, color)
    kwargs = {}
    if exif_datetime:
        exif = Image.Exif()
        exif[0x0132] = exif_datetime  # DateTime
        exif.get_ifd(0x8769)[0x9003] = exif_datetime  # DateTimeOriginal
        kwargs["exif"] = exif.tobytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", **kwargs)
    return path


@pytest.fixture
def image_factory():
    return make_image
