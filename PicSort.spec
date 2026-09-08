# PyInstaller build recipe. Run:  pyinstaller PicSort.spec
# Produces dist/PicSort.exe on Windows, dist/PicSort.app on macOS, dist/PicSort on Linux.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
root = Path(SPECPATH)

datas = [(str(root / "picsort" / "assets"), "picsort/assets")]
binaries = []
hiddenimports = []
for package in ("pillow_heif", "imagehash"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

icon = str(root / "picsort" / "assets" / ("icon.icns" if sys.platform == "darwin" else "icon.ico"))

a = Analysis(
    [str(root / "picsort.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["face_recognition", "sklearn", "scipy", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, exclude_binaries=True, name="PicSort", console=False, icon=icon)
    coll = COLLECT(exe, a.binaries, a.datas, name="PicSort")
    app = BUNDLE(
        coll,
        name="PicSort.app",
        icon=icon,
        bundle_identifier="com.danieljarnig.picsort",
        info_plist={"NSHighResolutionCapable": True, "LSMinimumSystemVersion": "12.0"},
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas,
        name="PicSort", console=False, icon=icon, upx=False,
    )
