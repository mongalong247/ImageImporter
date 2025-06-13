import sys
import os
import platform
import shutil
import zipfile
import urllib.request
import urllib.error
import subprocess
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QComboBox, QHBoxLayout,
    QProgressBar, QCheckBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, QApplication, QMessageBox
)
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# --- CONFIGURATION & PATHS ---

# Define the base directory for resources.
# This makes the script runnable from anywhere.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(APP_DIR, "resources")
# Ensure the resources directory exists.
os.makedirs(RESOURCES_DIR, exist_ok=True)

# Define the correct, cross-platform name for the ExifTool executable.
EXIFTOOL_EXE_NAME = "exiftool.exe" if platform.system() == "Windows" else "exiftool"
EXIFTOOL_PATH = os.path.join(RESOURCES_DIR, EXIFTOOL_EXE_NAME)

# --- EXIFTOOL DOWNLOAD MANAGER ---
# Code responsible for checking for and installing ExifTool.

def get_installed_exiftool_version():
    """Checks the version of the locally installed ExifTool."""
    if not os.path.exists(EXIFTOOL_PATH):
        return None
    try:
        # Use a fully qualified path to avoid PATH issues.
        output = subprocess.check_output([EXIFTOOL_PATH, "-ver"], text=True).strip()
        return output
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def get_latest_exiftool_version():
    """Fetches the latest ExifTool version number from the official website."""
    url = "https://exiftool.org/ver.txt"
    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode("utf-8").strip()
    except Exception as e:
        print(f"Error fetching latest ExifTool version: {e}")
        return None

def download_and_extract_exiftool(version):
    zip_path = os.path.join(RESOURCES_DIR, "exiftool.zip")
    url_templates = [
        f"https://exiftool.org/exiftool-{version}_64.zip",
        f"https://exiftool.org/exiftool-{version}.zip"
    ]

    # Attempt to download
    for url in url_templates:
        try:
            print(f"Attempting to download: {url}")
            urllib.request.urlretrieve(url, zip_path)
            print(f"Downloaded ExifTool v{version}.")
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"404 not found: {url}")
                continue
            raise
        except Exception as e:
            print(f"Download error: {e}")
            return False
    else:
        print("Failed to download ExifTool.")
        return False

    # Extract exe and exiftool_files
    try:
        found_exe = False
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for member in zip_ref.namelist():
                if member.lower().endswith(".exe") and "exiftool" in member.lower():
                    print(f"Found ExifTool EXE: {member}")
                    with zip_ref.open(member) as source, open(EXIFTOOL_PATH, "wb") as target:
                        shutil.copyfileobj(source, target)
                    found_exe = True
                elif member.startswith("exiftool_files/"):
                    zip_ref.extract(member, RESOURCES_DIR)

        if not found_exe:
            print("ExifTool executable not found in archive.")
            return False

        print(f"ExifTool v{version} installed successfully to {EXIFTOOL_PATH}")
        return True

    except Exception as e:
        print(f"Extraction error: {e}")
        return False

    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

def check_or_install_exiftool():
    """
    Checks if ExifTool is installed and up-to-date.
    If not, it attempts to download and install the latest version.
    """
    print("Checking for ExifTool...")
    latest_version = get_latest_exiftool_version()
    if not latest_version:
        print("Could not check for the latest ExifTool version. Will use existing version if available.")
        return os.path.exists(EXIFTOOL_PATH)

    installed_version = get_installed_exiftool_version()
    
    print(f"Latest version available: {latest_version}")
    print(f"Installed version: {installed_version or 'Not found'}")
    
    if installed_version == latest_version:
        print(f"ExifTool v{installed_version} is up to date.")
        return True
    
    print(f"Updating ExifTool from v{installed_version or 'N/A'} to v{latest_version}...")
    return download_and_extract_exiftool(latest_version)


# --- EXIF METADATA MANAGER ---
# Code responsible for reading and writing metadata using the ExifTool executable.

def write_metadata(file_path: str, metadata: dict) -> bool:
    """
    Writes EXIF metadata to a single file using the ExifTool executable.

    Args:
        file_path: The absolute path to the image file.
        metadata: A dictionary where keys are EXIF tag names (e.g., "LensModel")
                  and values are the data to be written.

    Returns:
        True if the operation was successful, False otherwise.
    """
    if not os.path.exists(file_path):
        print(f"[Error] File not found for metadata writing: {file_path}")
        return False

    # Start building the command-line arguments for ExifTool.
    args = [EXIFTOOL_PATH, "-overwrite_original"]
    
    # Add each metadata tag and value to the command.
    for tag, value in metadata.items():
        if value:  # Only add tags that have a non-empty value.
            args.append(f"-{tag}={value}")
    
    # Do not run exiftool if no tags were provided
    if len(args) <= 2:
        print(f"No metadata tags to write for {os.path.basename(file_path)}.")
        return True # Considered a success as there was nothing to do.

    args.append(file_path)

    try:
        # Execute the command.
        print(f"Running ExifTool for {os.path.basename(file_path)}...")
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        
        # Check for errors.
        if result.returncode != 0:
            print(f"[ExifTool Error] Failed to write metadata to {os.path.basename(file_path)}.")
            print(f"[ExifTool Error Output] {result.stderr.strip()}")
            return False
            
        print(f"Successfully wrote metadata to {os.path.basename(file_path)}.")
        return True
        
    except FileNotFoundError:
        print(f"[Exception] ExifTool not found at path: {EXIFTOOL_PATH}")
        return False
    except Exception as e:
        print(f"[Exception] An unexpected error occurred while writing metadata: {e}")
        return False

def get_shot_date(file_path: str) -> datetime | None:
    """
    Extracts the 'shot date' from a file's EXIF metadata using ExifTool.
    It prioritizes 'DateTimeOriginal' and falls back to 'CreateDate'.

    Args:
        file_path: The absolute path to the image file.

    Returns:
        A datetime object representing the shot date, or None if not found.
    """
    if not os.path.exists(file_path):
        return None

    try:
        # Command to extract the relevant date tags in JSON format.
        cmd = [EXIFTOOL_PATH, "-j", "-DateTimeOriginal", "-CreateDate", file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        
        metadata = json.loads(result.stdout)[0]
        date_str = metadata.get("DateTimeOriginal") or metadata.get("CreateDate")

        if date_str:
            # ExifTool returns dates in the format "YYYY:MM:DD HH:MM:SS".
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            
    except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError) as e:
        print(f"[Exif Error] Could not read shot date from {os.path.basename(file_path)}: {e}")
    except Exception as e:
        print(f"[Exif Error] An unexpected error occurred reading shot date: {e}")

    return None

# --- UTILITY FUNCTIONS ---

def truncate_path(path: str, max_len: int = 60) -> str:
    """Truncates a file path for display, showing the end of the path."""
    if len(path) <= max_len:
        return path
    return f"...{path[-(max_len - 3):]}"


# --- GUI: METADATA PANEL ---

class MetadataPanel(QGroupBox):
    """A QGroupBox widget for entering custom metadata."""
    def __init__(self):
        super().__init__("Metadata to Apply")
        self.layout = QGridLayout(self)

        # Create input fields for each metadata type.
        self.make_input = QLineEdit()
        self.model_input = QLineEdit()
        
        self.focal_input = QLineEdit()
        self.focal_input.setPlaceholderText("e.g., 85 or 85mm")
        
        self.aperture_input = QLineEdit()
        self.aperture_input.setPlaceholderText("e.g., 2.8 or f/2.8")

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("Optional lens serial number")

        self.notes_input = QTextEdit()
        
        # Add labels and widgets to the layout.
        self.layout.addWidget(QLabel("Lens Make:"), 0, 0)
        self.layout.addWidget(self.make_input, 0, 1)
        self.layout.addWidget(QLabel("Lens Model:"), 1, 0)
        self.layout.addWidget(self.model_input, 1, 1)
        self.layout.addWidget(QLabel("Focal Length:"), 2, 0)
        self.layout.addWidget(self.focal_input, 2, 1)
        self.layout.addWidget(QLabel("Aperture (F-Number):"), 3, 0)
        self.layout.addWidget(self.aperture_input, 3, 1)
        self.layout.addWidget(QLabel("Lens Serial:"), 4, 0)
        self.layout.addWidget(self.serial_input, 4, 1)
        self.layout.addWidget(QLabel("Notes/Description:"), 5, 0)
        self.layout.addWidget(self.notes_input, 5, 1, 2, 1)

    def get_metadata(self) -> dict:
        """
        Collects the data from the input fields and returns it as a dictionary.
        The dictionary keys are the actual ExifTool tag names.
        """
        return {
            "LensMake": self.make_input.text().strip(),
            "LensModel": self.model_input.text().strip(),
            "FocalLength": self.focal_input.text().strip(),
            "FNumber": self.aperture_input.text().strip(),
            "LensSerialNumber": self.serial_input.text().strip(),
            "ImageDescription": self.notes_input.toPlainText().strip()
        }

# --- BACKGROUND WORKER ---

class ImportWorker(QObject):
    """
    Handles the file import process in a separate thread to keep the UI responsive.
    """
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_folder, source_files, dest_folder, backup_folder, structure, metadata):
        super().__init__()
        self.source_folder = source_folder
        self.source_files = source_files
        self.dest_folder = dest_folder
        self.backup_folder = backup_folder
        self.structure = structure
        self.metadata = metadata
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        """The main logic for the import process."""
        try:
            # Determine the list of files to process.
            if self.source_files:
                image_paths = self.source_files
            else:
                image_paths = [
                    os.path.join(self.source_folder, f)
                    for f in os.listdir(self.source_folder)
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.cr2', '.nef', '.arw', '.dng', '.rw2'))
                ]

            total_files = len(image_paths)
            if total_files == 0:
                self.status.emit("No images found to import.")
                self.finished.emit()
                return

            self.status.emit(f"Found {total_files} image(s). Starting import...")

            for idx, file_path in enumerate(image_paths):
                if not self.is_running:
                    self.status.emit("Import cancelled by user.")
                    break
                    
                # 1. Determine destination subfolder based on user's choice.
                if self.structure == "Shot Date":
                    shot_date = get_shot_date(file_path)
                    subfolder_name = shot_date.strftime("%Y-%m-%d") if shot_date else "unknown_date"
                else:  # "Import Date"
                    subfolder_name = datetime.now().strftime("%Y-%m-%d")

                # 2. Create destination paths and copy the file.
                dest_path_with_subfolder = os.path.join(self.dest_folder, subfolder_name)
                os.makedirs(dest_path_with_subfolder, exist_ok=True)

                filename = os.path.basename(file_path)
                dest_file_path = os.path.join(dest_path_with_subfolder, filename)
                
                self.status.emit(f"Copying {filename} to primary...")
                shutil.copy2(file_path, dest_file_path)

                # 3. Handle backup if a folder is selected.
                if self.backup_folder:
                    backup_path_with_subfolder = os.path.join(self.backup_folder, subfolder_name)
                    os.makedirs(backup_path_with_subfolder, exist_ok=True)
                    self.status.emit(f"Copying {filename} to backup...")
                    shutil.copy2(file_path, os.path.join(backup_path_with_subfolder, filename))

                # 4. Apply metadata if any was provided.
                if self.metadata:
                    self.status.emit(f"Writing metadata for {filename}...")
                    success = write_metadata(dest_file_path, self.metadata)
                    if not success:
                        self.status.emit(f"Metadata write failed for {filename}")

                # 5. Update progress.
                progress_percent = int((idx + 1) / total_files * 100)
                self.progress.emit(progress_percent)
            
            if self.is_running:
                self.status.emit("Import complete.")
        except Exception as e:
            self.status.emit(f"Import process failed: {e}")
        finally:
            self.finished.emit()


# --- GUI: MAIN WINDOW ---

class ImageImporter(QWidget):
    """The main application window."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photo Import & Tagger")
        self.setGeometry(100, 100, 900, 600)
        
        self.layout = QHBoxLayout(self)
        self.source_folder = ""
        self.selected_files = []
        self.dest_folder = ""
        self.backup_folder = ""
        self.import_thread = None
        self.import_worker = None

        # Build the two main panels of the UI.
        self.metadata_panel = MetadataPanel()
        self.build_import_form()
        
        self.layout.addWidget(self.import_form_group)
        self.layout.addWidget(self.metadata_panel)
        self.metadata_panel.setVisible(False)

    def build_import_form(self):
        self.import_form_group = QGroupBox("Import Settings")
        self.import_layout = QVBoxLayout()
        self.import_form_group.setLayout(self.import_layout)

        # Source Selection
        self.source_button = QPushButton("1. Select Source (Files or Folder)")
        self.source_button.clicked.connect(self.select_source)
        self.source_path_label = QLabel("No source selected")
        self.source_path_label.setStyleSheet("color: gray; font-style: italic")

        # Destination Selection
        self.dest_button = QPushButton("2. Select Primary Destination")
        self.dest_button.clicked.connect(self.select_destination)
        self.dest_path_label = QLabel("No destination selected")
        self.dest_path_label.setStyleSheet("color: gray; font-style: italic")

        # Backup Selection
        self.backup_button = QPushButton("3. Select Backup Folder (Optional)")
        self.backup_button.clicked.connect(self.select_backup)
        self.backup_path_label = QLabel("No backup folder selected")
        self.backup_path_label.setStyleSheet("color: gray; font-style: italic")

        # Import Options
        self.structure_label = QLabel("Organize subfolders by:")
        self.structure_dropdown = QComboBox()
        self.structure_dropdown.addItems(["Shot Date", "Import Date"])
        
        self.metadata_toggle = QCheckBox("Apply custom metadata")
        self.metadata_toggle.toggled.connect(self.metadata_panel.setVisible)

        # Action Buttons & Status
        self.import_button = QPushButton("Start Import")
        self.import_button.setStyleSheet("font-weight: bold; padding: 8px;")
        self.import_button.clicked.connect(self.start_import)
        
        self.progress = QProgressBar()
        self.status_label = QLabel("Idle. Select source and destination to begin.")
        self.status_label.setWordWrap(True)

        # Add all widgets to the layout
        self.import_layout.addWidget(self.source_button)
        self.import_layout.addWidget(self.source_path_label)
        self.import_layout.addSpacing(15)
        self.import_layout.addWidget(self.dest_button)
        self.import_layout.addWidget(self.dest_path_label)
        self.import_layout.addSpacing(15)
        self.import_layout.addWidget(self.backup_button)
        self.import_layout.addWidget(self.backup_path_label)
        self.import_layout.addSpacing(20)
        self.import_layout.addWidget(self.structure_label)
        self.import_layout.addWidget(self.structure_dropdown)
        self.import_layout.addSpacing(10)
        self.import_layout.addWidget(self.metadata_toggle)
        self.import_layout.addStretch()
        self.import_layout.addWidget(self.import_button)
        self.import_layout.addWidget(self.status_label)
        self.import_layout.addWidget(self.progress)
        
    def select_source(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        # First, offer to select files.
        files, _ = dialog.getOpenFileNames(
            self,
            "Select Image Files (or Cancel to Choose a Folder)",
            "",
            "Images (*.jpg *.jpeg *.png *.cr2 *.nef *.arw *.dng *.rw2)"
        )
        if files:
            self.selected_files = files
            self.source_folder = ""  # Clear folder selection
            self.source_path_label.setText(f"{len(files)} file(s) selected")
            self.source_path_label.setToolTip("\n".join(files))
        else:
            # If the user cancelled, offer to select a folder instead.
            folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
            if folder:
                self.source_folder = folder
                self.selected_files = []  # Clear file selection
                display_path = truncate_path(folder)
                self.source_path_label.setText(display_path)
                self.source_path_label.setToolTip(folder)

    def select_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Primary Destination Folder")
        if folder:
            self.dest_folder = folder
            display_path = truncate_path(folder)
            self.dest_path_label.setText(display_path)
            self.dest_path_label.setToolTip(folder)

    def select_backup(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
        if folder:
            self.backup_folder = folder
            display_path = truncate_path(folder)
            self.backup_path_label.setText(display_path)
            self.backup_path_label.setToolTip(folder)
    
    def start_import(self):
        if not (self.selected_files or self.source_folder) or not self.dest_folder:
            self.status_label.setText("Error: A source (files or folder) and a primary destination must be selected.")
            return

        self.import_button.setEnabled(False)
        self.progress.setValue(0)
        self.status_label.setText("Starting import process...")

        metadata = self.metadata_panel.get_metadata() if self.metadata_toggle.isChecked() else {}

        # Create and start the worker thread.
        self.import_thread = QThread()
        self.import_worker = ImportWorker(
            source_folder=self.source_folder,
            source_files=self.selected_files,
            dest_folder=self.dest_folder,
            backup_folder=self.backup_folder,
            structure=self.structure_dropdown.currentText(),
            metadata=metadata
        )
        self.import_worker.moveToThread(self.import_thread)

        # Connect signals and slots for communication.
        self.import_thread.started.connect(self.import_worker.run)
        self.import_worker.progress.connect(self.progress.setValue)
        self.import_worker.status.connect(self.status_label.setText)
        self.import_worker.finished.connect(self.on_import_finished)
        
        self.import_thread.start()
        
    def on_import_finished(self):
        """Cleans up the thread and re-enables the UI."""
        self.import_thread.quit()
        self.import_thread.wait()
        self.import_button.setEnabled(True)
        self.import_thread = None
        self.import_worker = None
        
    def closeEvent(self, event):
        """Ensures the worker thread is stopped gracefully when closing the app."""
        if self.import_worker:
            self.import_worker.stop()
        if self.import_thread:
            self.import_thread.quit()
            self.import_thread.wait()
        event.accept()

# --- APPLICATION ENTRY POINT ---

if __name__ == "__main__":
    # First, ensure ExifTool is available before launching the GUI.
    if not check_or_install_exiftool():
        app = QApplication(sys.argv)
        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Icon.Critical)
        error_box.setText("ExifTool Installation Failed")
        error_box.setInformativeText("Could not install or find ExifTool. The application cannot continue.\n\nPlease ensure you have an internet connection or manually place 'exiftool.exe' in the 'resources' folder next to the application.")
        error_box.setWindowTitle("Critical Error")
        error_box.exec()
        sys.exit(1)

    # Launch the main application window.
    app = QApplication(sys.argv)
    importer = ImageImporter()
    importer.show()
    sys.exit(app.exec())
