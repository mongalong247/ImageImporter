#!/usr/bin/env python3
"""
Post-build step: copies the project's resources/ folder to sit directly
alongside the built executable, OUTSIDE PyInstaller's internal libs folder
(_internal/ on Windows/Linux onedir builds, Contents/Frameworks on macOS
app bundles).

Why this exists
----------------
resources/ holds things that must persist next to the app across runs:
the bundled ExifTool binary on Windows, and the user's saved lens presets.
paths.py resolves this location as:

    BASE_DIR = os.path.dirname(sys.executable)   # the folder the exe/app lives in
    RESOURCES_DIR = BASE_DIR / "resources"

If resources/ is instead added to PyInstaller via the spec's `datas=`,
PyInstaller 6+ nests it inside an internal libs folder (_internal/) rather
than next to the exe -- paths.py never looks there, so the bundled ExifTool
silently "goes missing" at runtime. That mismatch is the "_internal folder
breaks the resources folder" bug this project hit previously.

Keeping resources/ entirely outside the PyInstaller Analysis and copying it
here, as an explicit step *after* the build, sidesteps that permanently --
whatever PyInstaller's internal layout does (or changes to, in some future
version), this step always places resources/ next to the actual running
executable.

Usage
-----
Run from the repo root, after building with the spec:

    pyinstaller packaging/ImageImporter.spec --noconfirm --clean
    python packaging/copy_resources.py

On Windows this requires resources/exiftool.exe and resources/exiftool_files/
to already exist in the repo (see packaging/README.md for how the release
workflow fetches the pinned ExifTool build). On macOS/Linux it just ensures
an empty resources/ folder exists next to the app -- no ExifTool binary is
ever bundled there; the app's existing fallback chain (custom path -> system
PATH -> bundled) already handles "nothing bundled" gracefully and shows a
platform-appropriate install hint (see exiftool_manager.py:_get_install_hint).
"""
import os
import platform
import shutil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_RESOURCES = os.path.join(REPO_ROOT, "resources")
DIST_DIR = os.path.join(REPO_ROOT, "dist")
APP_NAME = "ImageImporter"


def find_app_dir() -> str:
    """Returns the folder that should contain resources/, next to the exe."""
    if platform.system() == "Darwin":
        macos_dir = os.path.join(DIST_DIR, f"{APP_NAME}.app", "Contents", "MacOS")
        if os.path.isdir(macos_dir):
            return macos_dir
        raise SystemExit(
            f"Expected macOS app bundle not found: {macos_dir}\n"
            "Did `pyinstaller packaging/ImageImporter.spec` run first?"
        )

    onedir = os.path.join(DIST_DIR, APP_NAME)
    if os.path.isdir(onedir):
        return onedir
    raise SystemExit(
        f"Expected PyInstaller onedir output not found: {onedir}\n"
        "Did `pyinstaller packaging/ImageImporter.spec` run first?"
    )


def main() -> None:
    target = find_app_dir()
    dest_resources = os.path.join(target, "resources")
    os.makedirs(dest_resources, exist_ok=True)

    if platform.system() == "Windows":
        exe_name = "exiftool.exe"
        if not os.path.isdir(SRC_RESOURCES) or not os.path.isfile(
            os.path.join(SRC_RESOURCES, exe_name)
        ):
            raise SystemExit(
                f"resources/{exe_name} not found in the repo.\n"
                "Windows builds need the bundled ExifTool present before "
                "packaging -- see packaging/README.md ('Sourcing ExifTool "
                "for Windows builds')."
            )
        for name in os.listdir(SRC_RESOURCES):
            if name == "lens_presets.json":
                # This is a user's personal saved-preset data, never ship a
                # stale dev copy of it in a release build.
                continue
            src = os.path.join(SRC_RESOURCES, name)
            dst = os.path.join(dest_resources, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        print(f"Copied Windows resources/ (incl. bundled ExifTool) to: {dest_resources}")
    else:
        print(
            f"Created empty resources/ at: {dest_resources}\n"
            "No ExifTool bundled on this platform by design -- users install "
            "it via Homebrew/apt/dnf/pacman, or point the app at a custom "
            "path from Settings > Set ExifTool Path..."
        )


if __name__ == "__main__":
    main()
