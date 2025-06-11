import requests

def check_exiftool_update(current_version):
    try:
        url = "https://api.github.com/repos/exiftool/exiftool/releases/latest"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest_version = data["tag_name"].lstrip("v")  # e.g., "12.70"
            if latest_version != current_version:
                print(f"[!] A new version of ExifTool is available: {latest_version}")
                print("Visit https://github.com/exiftool/exiftool/releases to download the latest release.")
            else:
                print("[✓] ExifTool is up to date.")
        else:
            print("[!] Failed to check for updates.")
    except Exception as e:
        print(f"[!] Error checking for ExifTool updates: {e}")
