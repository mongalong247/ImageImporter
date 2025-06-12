import os
import platform
import shutil
import zipfile
import urllib.request

# Define paths
RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")
EXIFTOOL_EXE = os.path.join(RESOURCES_DIR, "exiftool.exe" if platform.system() == "Windows" else "exiftool")

# Version check URLs
VER_TXT_URL = "https://exiftool.org/ver.txt"
ZIP_URL_TEMPLATE = "https://exiftool.org/exiftool-{}_64.zip"

def get_installed_version():
    if not os.path.exists(EXIFTOOL_EXE):
        return None
    try:
        output = os.popen(f'"{EXIFTOOL_EXE}" -ver').read().strip()
        return output if output else None
    except Exception:
        return None

def get_latest_version():
    try:
        with urllib.request.urlopen(VER_TXT_URL) as response:
            return response.read().decode("utf-8").strip()
    except Exception as e:
        print("Error fetching latest ExifTool version:", e)
        return None

def download_and_extract_exiftool(version):
    try:
        zip_url = ZIP_URL_TEMPLATE.format(version)
        zip_path = os.path.join(RESOURCES_DIR, "exiftool.zip")
        print(f"Downloading ExifTool v{version}...")
        urllib.request.urlretrieve(zip_url, zip_path)

        extract_path = os.path.join(RESOURCES_DIR, f"exiftool-{version}")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        # Locate and move binary to RESOURCES_DIR
        binary_name = "exiftool.exe" if platform.system() == "Windows" else "exiftool"
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                if file.lower().startswith("exiftool") and file.lower().endswith(".exe" if platform.system() == "Windows" else ""):
                    source_path = os.path.join(root, file)
                    shutil.move(source_path, EXIFTOOL_EXE)
                    break

        # Clean up
        shutil.rmtree(extract_path)
        os.remove(zip_path)

        print(f"ExifTool v{version} installed successfully to {EXIFTOOL_EXE}")
        return True
    except Exception as e:
        print("Error installing ExifTool:", e)
        return False

def check_or_install_exiftool():
    latest_version = get_latest_version()
    if not latest_version:
        print("Could not check latest version. Proceeding with current install.")
        return os.path.exists(EXIFTOOL_EXE)

    installed_version = get_installed_version()
    if installed_version == latest_version:
        print(f"ExifTool v{installed_version} is up to date.")
        return True
    elif installed_version:
        print(f"Updating ExifTool from v{installed_version} to v{latest_version}...")
    else:
        print(f"Installing ExifTool v{latest_version}...")

    return download_and_extract_exiftool(latest_version)
