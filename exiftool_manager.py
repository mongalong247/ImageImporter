import os
import platform
import shutil
import zipfile
import urllib.request
import urllib.error
import subprocess
import json
from datetime import datetime

# --- PATHS & CONFIGURATION ---

# Define paths relative to this file's location.
RESOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
# Define the platform-specific executable name.
EXIFTOOL_EXE_NAME = "exiftool.exe" if platform.system() == "Windows" else "exiftool"
# Define the full, absolute path to the executable.
EXIFTOOL_PATH = os.path.join(RESOURCES_DIR, EXIFTOOL_EXE_NAME)

# --- PUBLIC FUNCTIONS ---

def check_or_install_exiftool():
    """
    Checks if ExifTool is installed and up-to-date. This is the main public
    function to be called by the main application.
    """
    # Ensure the resources directory exists before we do anything.
    os.makedirs(RESOURCES_DIR, exist_ok=True)
    
    print("Checking for ExifTool...")
    latest_version = _get_latest_version()
    if not latest_version:
        print("Could not check for the latest ExifTool version. Will use the existing version if available.")
        return os.path.exists(EXIFTOOL_PATH)

    installed_version = _get_installed_version()
    
    print(f"Latest version available: {latest_version}")
    print(f"Installed version: {installed_version or 'Not found'}")
    
    if installed_version and installed_version >= latest_version:
        print(f"ExifTool v{installed_version} is up to date.")
        return True
    
    print(f"Updating ExifTool from v{installed_version or 'N/A'} to v{latest_version}...")
    return _download_and_extract_exiftool(latest_version)

def write_metadata(file_path: str, metadata: dict) -> bool:
    """
    Writes EXIF metadata to a single file using the ExifTool executable.
    """
    if not os.path.exists(file_path):
        print(f"[Error] File not found for metadata writing: {file_path}")
        return False

    args = [EXIFTOOL_PATH, "-overwrite_original"]
    for tag, value in metadata.items():
        if value:
            args.append(f"-{tag}={value}")
    
    if len(args) <= 2:
        return True # Nothing to write, which is a success.

    args.append(file_path)

    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"[ExifTool Error] {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        print(f"[Exception] Failed to write metadata: {e}")
        return False

def get_shot_date(file_path: str) -> datetime | None:
    """
    Extracts the 'shot date' from a file's EXIF metadata using ExifTool.
    """
    if not os.path.exists(file_path):
        return None
    try:
        cmd = [EXIFTOOL_PATH, "-j", "-DateTimeOriginal", "-CreateDate", file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        metadata = json.loads(result.stdout)[0]
        date_str = metadata.get("DateTimeOriginal") or metadata.get("CreateDate")
        if date_str:
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        print(f"[Exif Error] Could not read shot date from {os.path.basename(file_path)}: {e}")
    return None

# --- INTERNAL HELPER FUNCTIONS ---

def _get_installed_version():
    """Checks the version of the locally installed ExifTool."""
    if not os.path.exists(EXIFTOOL_PATH):
        return None
    try:
        # Use a fully qualified path to avoid PATH issues.
        output = subprocess.check_output([EXIFTOOL_PATH, "-ver"], text=True).strip()
        return output
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def _get_latest_version():
    """Fetches the latest ExifTool version number from the official website."""
    url = "https://exiftool.org/ver.txt"
    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode("utf-8").strip()
    except Exception as e:
        print(f"Error fetching latest ExifTool version: {e}")
        return None

def _download_and_extract_exiftool(version):
    """
    Downloads and extracts ExifTool using your original, robust logic.
    This includes creating a temporary extraction folder and moving the
    necessary files into the resources directory.
    """
    zip_path = os.path.join(RESOURCES_DIR, "exiftool.zip")
    extract_path = os.path.join(RESOURCES_DIR, f"exiftool-temp-{version}")
    
    # Use the URL template from your original script.
    zip_url = f"https://exiftool.org/exiftool-{version}_64.zip"
    
    try:
        print(f"Downloading ExifTool v{version} from {zip_url}...")
        urllib.request.urlretrieve(zip_url, zip_path)

        # Extract to a temporary folder.
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        # Locate and move the main executable.
        binary_moved = False
        for root, _, files in os.walk(extract_path):
            for file in files:
                if file.lower().startswith("exiftool") and file.lower().endswith(".exe"):
                    source_path = os.path.join(root, file)
                    shutil.move(source_path, EXIFTOOL_PATH)
                    binary_moved = True
                    break
            if binary_moved:
                break
        
        if not binary_moved:
            raise FileNotFoundError("Could not find exiftool.exe in the extracted files.")

        print(f"ExifTool v{version} installed successfully.")
        return True

    except Exception as e:
        print(f"Error during ExifTool installation: {e}")
        return False
    finally:
        # Clean up temporary files and folders.
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        if os.path.exists(zip_path):
            os.remove(zip_path)
