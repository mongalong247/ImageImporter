#!/usr/bin/env python3
"""
Generates assets/app_icon.icns from assets/app_icon.ico, for macOS builds.

Uses Pillow (already a project dependency -- see requirements.txt) to do
the actual image resizing/conversion, rather than macOS's `sips`. `sips`
has inconsistent support for reading multi-resolution .ico files across
macOS versions -- it failed outright in this project's release workflow
("Unable to write image ... Error 13") on its first real run. Pillow's ICO
reader is predictable and keeps this pipeline in Python instead of leaning
on a flaky platform CLI tool.

`iconutil` (building the final .icns from a folder of PNGs) has no good
pure-Python equivalent and is macOS-only, so this script must run on macOS.

Usage (from repo root, on macOS, after `pip install -r requirements.txt`):
    python packaging/make_macos_icon.py
"""
import os
import subprocess
import sys

from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ICO = os.path.join(REPO_ROOT, "assets", "app_icon.ico")
ICONSET_DIR = os.path.join(REPO_ROOT, "AppIcon.iconset")
DEST_ICNS = os.path.join(REPO_ROOT, "assets", "app_icon.icns")

# Standard macOS iconset sizes (base + @2x retina variant of each).
SIZES = (16, 32, 128, 256, 512)


def main() -> None:
    if sys.platform != "darwin":
        raise SystemExit("make_macos_icon.py must be run on macOS (it shells out to iconutil).")
    if not os.path.isfile(SRC_ICO):
        raise SystemExit(f"Source icon not found: {SRC_ICO}")

    os.makedirs(ICONSET_DIR, exist_ok=True)

    # Pillow's ICO reader picks the largest embedded frame by default --
    # that's what we want as the source to scale every target size from.
    source = Image.open(SRC_ICO).convert("RGBA")

    for size in SIZES:
        source.resize((size, size), Image.LANCZOS).save(
            os.path.join(ICONSET_DIR, f"icon_{size}x{size}.png")
        )
        double = size * 2
        source.resize((double, double), Image.LANCZOS).save(
            os.path.join(ICONSET_DIR, f"icon_{size}x{size}@2x.png")
        )

    subprocess.run(["iconutil", "-c", "icns", ICONSET_DIR, "-o", DEST_ICNS], check=True)
    print(f"Wrote {DEST_ICNS}")


if __name__ == "__main__":
    main()