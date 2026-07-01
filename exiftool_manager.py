import os
import platform
import shutil
import zipfile
import urllib.request
import urllib.error
import subprocess
import json
from datetime import datetime

from PyQt6.QtCore import QSettings

import paths

# --- PATHS & CONFIGURATION ---

RESOURCES_DIR = paths.RESOURCES_DIR
EXIFTOOL_EXE_NAME = "exiftool.exe" if platform.system() == "Windows" else "exiftool"
BUNDLED_EXIFTOOL_PATH = os.path.join(RESOURCES_DIR, EXIFTOOL_EXE_NAME)

# Kept for backwards compatibility with any code that still references the
# old constant name directly (e.g. error messages).
EXIFTOOL_PATH = BUNDLED_EXIFTOOL_PATH

SETTINGS_ORG = "PhotoTagger"
SETTINGS_APP = "ImageImporter"
CUSTOM_PATH_KEY = "exiftoolCustomPath"

# --- Platform-specific configuration for subprocess to hide console window ---
SUBPROCESS_ARGS = {}
if platform.system() == "Windows":
    SUBPROCESS_ARGS['creationflags'] = subprocess.CREATE_NO_WINDOW

NETWORK_TIMEOUT = 10  # seconds, for version-check and download requests
SUBPROCESS_TIMEOUT = 15  # seconds, for calls to the exiftool binary itself

# --- State ---
_resolved_exiftool_path = None  # cached once a working path is found this session
_exiftool_checked = False       # guards against repeating the full resolve/download flow


# --- SETTINGS: CUSTOM PATH ---

def get_custom_path() -> str:
    """Returns the user-configured custom ExifTool path, or '' if unset."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return settings.value(CUSTOM_PATH_KEY, "", type=str)


def set_custom_path(path: str):
    """
    Saves a user-configured custom ExifTool path and forces re-resolution
    on the next call to resolve_exiftool_path() / ensure_exiftool_available().
    Pass an empty string to clear the override.
    """
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(CUSTOM_PATH_KEY, path)
    global _resolved_exiftool_path, _exiftool_checked
    _resolved_exiftool_path = None
    _exiftool_checked = False


# --- PUBLIC: RESOLUTION ---

def _is_valid_exiftool(path: str) -> bool:
    """Checks that `path` points to a file that actually runs as ExifTool."""
    if not path or not os.path.isfile(path):
        return False
    try:
        subprocess.check_output(
            [path, "-ver"], text=True, timeout=SUBPROCESS_TIMEOUT, **SUBPROCESS_ARGS
        )
        return True
    except Exception:
        return False


def resolve_exiftool_path():
    """
    Resolves a working ExifTool executable using a fallback chain, without
    attempting any download:
      1. User-configured custom path (Settings)
      2. A system-wide install found on PATH
      3. The bundled copy in resources/

    Returns the resolved path (str), or None if nothing usable was found.
    """
    global _resolved_exiftool_path

    if _resolved_exiftool_path and _is_valid_exiftool(_resolved_exiftool_path):
        return _resolved_exiftool_path

    custom = get_custom_path()
    if custom and _is_valid_exiftool(custom):
        _resolved_exiftool_path = custom
        return custom

    system_path = shutil.which("exiftool")
    if system_path and _is_valid_exiftool(system_path):
        _resolved_exiftool_path = system_path
        return system_path

    if _is_valid_exiftool(BUNDLED_EXIFTOOL_PATH):
        _resolved_exiftool_path = BUNDLED_EXIFTOOL_PATH
        return BUNDLED_EXIFTOOL_PATH

    _resolved_exiftool_path = None
    return None


def get_active_exiftool_path():
    """Returns the currently cached, resolved exiftool path (may be None)."""
    return _resolved_exiftool_path


def ensure_exiftool_available():
    """
    Makes a best effort to have a working ExifTool ready to use. Tries the
    fallback chain first; only attempts a download if nothing was found.

    This function NEVER raises and never decides the app should quit -- it
    just reports what it found so the caller can degrade gracefully (e.g.
    disable metadata features) instead of treating a missing ExifTool as
    fatal.

    Returns (success: bool, message: str).
    """
    global _exiftool_checked

    if _exiftool_checked:
        path = resolve_exiftool_path()
        return (path is not None), (f"Using ExifTool at: {path}" if path else "ExifTool not found.")

    path = resolve_exiftool_path()
    if path:
        _exiftool_checked = True
        return True, f"Using ExifTool at: {path}"

    # Nothing found via custom path, system PATH, or bundled copy.
    # Only Windows has an automated download path today (see note below).
    os.makedirs(RESOURCES_DIR, exist_ok=True)

    if platform.system() != "Windows":
        _exiftool_checked = True
        return False, (
            "ExifTool was not found. Automatic download is currently only "
            "supported on Windows. Please install ExifTool for your platform "
            "(e.g. 'brew install exiftool' on macOS) or set a custom path in "
            "Settings > ExifTool Path."
        )

    latest_version = _get_latest_version()
    if not latest_version:
        _exiftool_checked = True
        return False, (
            "ExifTool was not found, and the latest version could not be "
            "checked (are you online?). You can set a custom path to an "
            "existing ExifTool install in Settings > ExifTool Path."
        )

    success = _download_and_extract_exiftool(latest_version)
    _exiftool_checked = True
    if success:
        global _resolved_exiftool_path
        _resolved_exiftool_path = BUNDLED_EXIFTOOL_PATH
        return True, f"ExifTool v{latest_version} installed successfully."

    return False, (
        f"Failed to download ExifTool v{latest_version} automatically. "
        "You can set a custom path to an existing ExifTool install in "
        "Settings > ExifTool Path."
    )


def check_or_install_exiftool() -> bool:
    """
    Deprecated alias kept for backwards compatibility. Prefer
    ensure_exiftool_available(), which also returns a status message and
    never implies the app must exit on failure.
    """
    success, _ = ensure_exiftool_available()
    return success


# --- PUBLIC: METADATA OPERATIONS ---

def write_metadata(file_path: str, metadata: dict) -> bool:
    """
    Writes EXIF metadata to a single file using the resolved ExifTool
    executable. Returns False (without raising) if no ExifTool is
    available or the file doesn't exist.
    """
    exiftool_path = resolve_exiftool_path()
    if not exiftool_path:
        print("[Error] ExifTool is not available; cannot write metadata.")
        return False

    if not os.path.exists(file_path):
        print(f"[Error] File not found for metadata writing: {file_path}")
        return False

    args = [exiftool_path, "-overwrite_original"]
    for tag, value in metadata.items():
        if value:
            args.append(f"-{tag}={value}")

    if len(args) <= 2:
        return True

    args.append(file_path)

    try:
        result = subprocess.run(
            args, capture_output=True, text=True, check=False,
            timeout=SUBPROCESS_TIMEOUT, **SUBPROCESS_ARGS
        )
        if result.returncode != 0:
            print(f"[ExifTool Error] {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        print(f"[Exception] Failed to write metadata: {e}")
        return False


def get_shot_date(file_path: str):
    """
    Extracts the 'shot date' from a file's EXIF metadata using ExifTool.
    Returns None (without raising) if no ExifTool is available, the file
    doesn't exist, or the date can't be parsed.
    """
    exiftool_path = resolve_exiftool_path()
    if not exiftool_path or not os.path.exists(file_path):
        return None
    try:
        cmd = [exiftool_path, "-j", "-DateTimeOriginal", "-CreateDate", file_path]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            check=True, timeout=SUBPROCESS_TIMEOUT, **SUBPROCESS_ARGS
        )
        metadata = json.loads(result.stdout)[0]
        date_str = metadata.get("DateTimeOriginal") or metadata.get("CreateDate")
        if date_str:
            # Some cameras include a timezone offset or subseconds; only the
            # first 19 characters ("YYYY:MM:DD HH:MM:SS") are guaranteed to
            # match this format, so trim before parsing.
            return datetime.strptime(date_str[:19], "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        print(f"[Exif Error] Could not read shot date from {os.path.basename(file_path)}: {e}")
    return None


# --- INTERNAL HELPER FUNCTIONS ---

def _get_installed_version():
    """Checks the version of the currently-resolved ExifTool, if any."""
    path = resolve_exiftool_path()
    if not path:
        return None
    try:
        output = subprocess.check_output(
            [path, "-ver"], text=True, timeout=SUBPROCESS_TIMEOUT, **SUBPROCESS_ARGS
        ).strip()
        return output
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _get_latest_version():
    """Fetches the latest ExifTool version number from the official website."""
    url = "https://exiftool.org/ver.txt"
    try:
        with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT) as response:
            return response.read().decode("utf-8").strip()
    except Exception as e:
        print(f"Error fetching latest ExifTool version: {e}")
        return None


def _download_and_extract_exiftool(version: str) -> bool:
    """
    Downloads and extracts ExifTool (Windows only), moving the executable
    and support files into RESOURCES_DIR.
    """
    zip_path = os.path.join(RESOURCES_DIR, "exiftool.zip")
    extract_path = os.path.join(RESOURCES_DIR, f"exiftool-temp-{version}")

    zip_url = f"https://exiftool.org/exiftool-{version}_64.zip"

    try:
        print(f"Downloading ExifTool v{version} from {zip_url}...")
        with urllib.request.urlopen(zip_url, timeout=NETWORK_TIMEOUT) as response:
            with open(zip_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        binary_moved = False
        for root, _, files in os.walk(extract_path):
            for file in files:
                if file.lower().startswith("exiftool") and file.lower().endswith(".exe"):
                    shutil.move(os.path.join(root, file), BUNDLED_EXIFTOOL_PATH)
                    binary_moved = True
                    break
            if binary_moved:
                break

        if not binary_moved:
            raise FileNotFoundError("Could not find exiftool.exe in the extracted files.")

        support_dir_moved = False
        for root, dirs, _ in os.walk(extract_path):
            for dir_name in dirs:
                if dir_name.lower() == "exiftool_files":
                    src = os.path.join(root, dir_name)
                    dst = os.path.join(RESOURCES_DIR, dir_name)
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.move(src, dst)
                    support_dir_moved = True
                    break
            if support_dir_moved:
                break

        print(f"ExifTool v{version} installed successfully.")
        return True

    except Exception as e:
        print(f"Error during ExifTool installation: {e}")
        return False
    finally:
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        if os.path.exists(zip_path):
            os.remove(zip_path)
