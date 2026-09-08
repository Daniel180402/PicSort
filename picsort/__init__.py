"""PicSort - sort, deduplicate and clean up large photo collections."""

__version__ = "2.0.0"

try:  # HEIC/HEIF photos from iPhones need this plug-in for Pillow
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:  # pragma: no cover - depends on optional install
    HEIF_SUPPORTED = False
