import subprocess
import os
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

EXIFTOOL_PATH = r"C:\\Users\\ianwa\\Documents\\ImageImporter\\resources\\exiftool.exe"  # Replace with the full path to the ExifTool executable

def write_metadata(file_path, metadata: dict) -> bool:
    """
    Write EXIF metadata to a file using exiftool.
    """
    if not os.path.exists(file_path):
        log.error(f"File not found: {file_path}")
        return False

    args = [EXIFTOOL_PATH, "-overwrite_original"]
    for tag, value in metadata.items():
        if value:  # Only add if there's a value
            args.append(f"-{tag}={value}")
    args.append(file_path)

    log.debug(f"Running command: {' '.join(args)}")

    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        if process.returncode!= 0:
            log.error(f"ExifTool error:\n{error.decode('utf-8')}")
            return False

        log.info(f"Metadata written successfully to: {file_path}")
        return True

    except Exception as e:
        log.exception(f"Exception during metadata write: {e}")
        return False