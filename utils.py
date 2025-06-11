import os
from datetime import datetime

def truncate_path(path: str, max_len: int = 50) -> str:
    """
    Truncate a file path for display, keeping only the end if it's too long.
    """
    return path if len(path) <= max_len else f"...{path[-(max_len - 3):]}"

def format_date(timestamp: float) -> str:
    """
    Format a timestamp into a YYYY-MM-DD string.
    """
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

def list_files(folder: str) -> list:
    """
    Return a list of file names (not directories) in the given folder.
    """
    return [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
