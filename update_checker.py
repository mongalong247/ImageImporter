import requests

def check_exiftool_update(current_version):
    try:
        response = requests.get("https://api.github.com/repos/exiftool/exiftool/releases/latest", timeout=5)
        response.raise_for_status()
        latest = response.json()["tag_name"].lstrip("v")
        if latest != current_version:
            print(f"[INFO] A new ExifTool version is available: {latest} (You have {current_version})")
        else:
            print("[INFO] ExifTool is up to date.")
    except requests.RequestException:
        print("[INFO] Could not check for ExifTool updates. Skipping.")
