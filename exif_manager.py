import subprocess
import os

EXIFTOOL_PATH = os.path.join("resources", "exiftool.exe")  # Adjust for Mac/Linux if needed

def write_metadata(file_path, metadata: dict) -> bool:
    """
    Write EXIF metadata to a file using exiftool.
    """
    if not os.path.exists(file_path):
        return False

    args = [EXIFTOOL_PATH]
    for tag, value in metadata.items():
        if value:
            args.append(f"-{tag}={value}")
    args.append(file_path)

    try:
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False
