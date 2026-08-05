# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for ImageImporter. Builds a "onedir" bundle on every
# platform (never --onefile): onefile re-extracts the whole app to a fresh
# temp folder on every launch, which is actively wrong for this app since
# exiftool_manager.py runs a POOL OF PERSISTENT ExifTool PROCESSES against
# resources/exiftool.exe -- that needs to be a stable, known path across the
# app's whole run, not something living in a temp folder that could vanish
# mid-session.
#
# Deliberately does NOT add resources/ (exiftool.exe, exiftool_files/,
# lens_presets.json) via `datas=`. That folder holds things that must sit
# in a stable, persistent location next to the actual executable --
# paths.py resolves BASE_DIR as os.path.dirname(sys.executable), and
# RESOURCES_DIR as BASE_DIR/resources. PyInstaller 6+ nests `datas=` entries
# inside an internal libs folder (_internal/ on Windows/Linux onedir
# builds) instead of next to the exe -- that mismatch is the "_internal
# folder breaks the resources folder" bug this project hit before. Instead,
# packaging/copy_resources.py copies resources/ into place as an explicit
# step AFTER this spec runs, so it always lands next to the real exe
# regardless of how PyInstaller's internal layout looks in any given
# version.
#
# assets/ (just the window icon) is fine to bundle normally via `datas=`
# below -- it's read-only and only ever read through app.py's
# resource_path() helper (sys._MEIPASS-based), which was designed for
# exactly this.
#
# Usage (from the repo root, on the target OS -- PyInstaller does not
# cross-compile):
#   pip install -r requirements.txt -r requirements-build.txt
#   pyinstaller packaging/ImageImporter.spec --noconfirm --clean
#   python packaging/copy_resources.py
#
# See packaging/README.md for the full release process, including how
# Windows builds get resources/exiftool.exe before this runs.

import os
import sys

APP_NAME = "ImageImporter"
REPO_ROOT = os.path.dirname(os.path.abspath(SPECPATH))

block_cipher = None

# Windows-only icon for the .exe itself. macOS's equivalent (.icns) is
# applied to the BUNDLE() below instead -- EXE()'s icon= is a Windows/exe
# concept.
win_icon = os.path.join(REPO_ROOT, "assets", "app_icon.ico")
mac_icon = os.path.join(REPO_ROOT, "assets", "app_icon.icns")

a = Analysis(
    [os.path.join(REPO_ROOT, "app.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[
        (os.path.join(REPO_ROOT, "assets"), "assets"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=win_icon if sys.platform == "win32" and os.path.isfile(win_icon) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=mac_icon if os.path.isfile(mac_icon) else None,
        bundle_identifier="nz.wakefield.imageimporter",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": os.environ.get("APP_VERSION", "0.0.0"),
            "CFBundleVersion": os.environ.get("APP_VERSION", "0.0.0"),
            "NSHumanReadableCopyright": "ImageImporter",
        },
    )
