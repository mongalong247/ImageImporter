import subprocess
import os
import json
from datetime import datetime

EXIFTOOL_PATH = os.path.join("resources", "exiftool.exe")  # Adjust for Mac/Linux if needed

def write_metadata(file_path, metadata: dict) -> bool:
    """
    Write EXIF metadata to a file using exiftool.
    """
    if not os.path.exists(file_path):
        print(f"[Error] File not found: {file_path}")
        return False

    args = [EXIFTOOL_PATH, "-overwrite_original"]
    for tag, value in metadata.items():
        if value:  # Only add if there's a value
            args.append(f"-{tag}={value}")
    args.append(file_path)

    try:
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ExifTool Error] {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        print(f"[Exception] Failed to write metadata: {e}")
        return False

def get_shot_date(file_path):
    """
    Extracts the shot date from EXIF metadata using exiftool.
    Tries DateTimeOriginal, then CreateDate. Returns datetime object or None.
    """
    if not os.path.exists(file_path):
        return None

    try:
        result = subprocess.run(
            [EXIFTOOL_PATH, "-j", "-DateTimeOriginal", "-CreateDate", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        metadata = json.loads(result.stdout)[0]
        date_str = metadata.get("DateTimeOriginal") or metadata.get("CreateDate")

        if date_str:
            # ExifTool returns format: "YYYY:MM:DD HH:MM:SS"
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        print(f"[Exif Error] {file_path}: {e}")

    return None
