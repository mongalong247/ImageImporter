import sys
import os
import shutil
import json
import platform
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QComboBox, QHBoxLayout,
    QProgressBar, QCheckBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, QApplication, QMessageBox
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QSettings

# --- Modular Imports ---
import exiftool_manager
from metadata_panel import MetadataManagerPanel

# --- CONSTANTS ---
APP_VERSION = "1.0.1"
# Styles for validation feedback
NORMAL_STYLE = "color: gray; font-style: italic;"
ERROR_STYLE = "color: #d32f2f; font-weight: bold;" # A material design red

# --- UTILITY FUNCTIONS ---

def truncate_path(path: str, max_len: int = 60) -> str:
    """Truncates a long path for display."""
    return path if len(path) <= max_len else f"...{path[-(max_len - 3):]}"

def open_folder(path):
    """Opens a folder in the default file explorer in a cross-platform way."""
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin": # macOS
        subprocess.run(["open", path])
    else: # Linux
        subprocess.run(["xdg-open", path])

# --- BACKGROUND WORKER ---

class ImportWorker(QObject):
    # (This class remains unchanged)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_folder, source_files, dest_folder, backup_folder, structure, date_format, metadata):
        super().__init__()
        self.source_folder = source_folder
        self.source_files = source_files
        self.dest_folder = dest_folder
        self.backup_folder = backup_folder
        self.structure = structure
        self.date_format = date_format
        self.metadata = metadata
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            image_paths = self.source_files or [os.path.join(self.source_folder, f) for f in os.listdir(self.source_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.cr2', '.nef', '.arw', '.dng', '.rw2'))]
            total_files = len(image_paths)
            if total_files == 0:
                self.status.emit("No compatible image files found to import.")
                self.finished.emit()
                return
            self.status.emit(f"Starting import of {total_files} file(s)...")
            for idx, file_path in enumerate(image_paths):
                if not self.is_running:
                    self.status.emit("Import cancelled by user.")
                    break
                if self.structure == "Shot Date":
                    shot_date = exiftool_manager.get_shot_date(file_path)
                    subfolder_name = shot_date.strftime(self.date_format) if shot_date else "unknown_date"
                else:
                    subfolder_name = datetime.now().strftime(self.date_format)
                dest_path_with_subfolder = os.path.join(self.dest_folder, subfolder_name)
                os.makedirs(dest_path_with_subfolder, exist_ok=True)
                filename = os.path.basename(file_path)
                dest_file_path = os.path.join(dest_path_with_subfolder, filename)
                self.status.emit(f"Copying {filename}...")
                shutil.copy2(file_path, dest_file_path)
                if self.backup_folder:
                    backup_path_with_subfolder = os.path.join(self.backup_folder, subfolder_name)
                    os.makedirs(backup_path_with_subfolder, exist_ok=True)
                    shutil.copy2(file_path, os.path.join(backup_path_with_subfolder, filename))
                if self.metadata:
                    self.status.emit(f"Applying metadata to {filename}...")
                    if not exiftool_manager.write_metadata(dest_file_path, self.metadata):
                         self.status.emit(f"Warning: Metadata write failed for {filename}")
                self.progress.emit(int((idx + 1) / total_files * 100))
            if self.is_running:
                self.status.emit("Import complete.")
        except Exception as e:
            self.status.emit(f"Import process failed: {e}")
        finally:
            self.finished.emit()

# --- GUI: MAIN WINDOW ---

class ImageImporter(QMainWindow):
    """The main application window."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photo Import & Tagger")
        self.setGeometry(100, 100, 900, 600)
        self.settings = QSettings("PhotoTagger", "ImageImporter")
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QHBoxLayout(central_widget)

        self.source_folder = ""
        self.selected_files = []
        self.dest_folder = ""
        self.backup_folder = ""
        self.import_thread = None
        self.import_worker = None

        self.metadata_panel = MetadataManagerPanel()
        self.build_import_form()
        
        self._create_menu_bar()

        self.layout.addWidget(self.import_form_group)
        self.layout.addWidget(self.metadata_panel)
        self.metadata_panel.setVisible(False)
        
        self.load_settings()

    def build_import_form(self):
        self.import_form_group = QGroupBox("Import Settings")
        self.import_layout = QVBoxLayout()
        self.import_form_group.setLayout(self.import_layout)

        source_group_label = QLabel("1. Choose Source:")
        self.select_files_button = QPushButton("Select Files...")
        self.select_files_button.clicked.connect(self.select_source_files)
        self.select_folder_button = QPushButton("Select Folder...")
        self.select_folder_button.clicked.connect(self.select_source_folder)
        source_button_layout = QHBoxLayout()
        source_button_layout.addWidget(self.select_files_button)
        source_button_layout.addWidget(self.select_folder_button)
        self.source_path_label = QLabel("No source selected")
        self.source_path_label.setStyleSheet(NORMAL_STYLE)

        dest_label = QLabel("2. Choose Destinations:")
        self.dest_button = QPushButton("Primary Destination...")
        self.dest_button.clicked.connect(self.select_destination)
        self.dest_path_label = QLabel("No destination selected")
        self.dest_path_label.setStyleSheet(NORMAL_STYLE)
        self.backup_button = QPushButton("Backup Destination... (Optional)")
        self.backup_button.clicked.connect(self.select_backup)
        self.backup_path_label = QLabel("No backup folder selected")
        self.backup_path_label.setStyleSheet(NORMAL_STYLE)
        
        date_format_label = QLabel("Folder Date Format:")
        self.date_format_combo = QComboBox()
        self.date_format_combo.setEditable(True)
        date_formats = ["YYYY-MM-DD", "YYYYMMDD", "YYYY-MM", "YYYY/MM-DD"]
        self.date_format_combo.addItems(date_formats)
        self.date_format_combo.setToolTip("Use YYYY, MM, DD to define folder names.\nExample: 'Photos/YYYY/MM' will be converted to Python's strftime format.")

        self.structure_label = QLabel("Organize subfolders by:")
        self.structure_dropdown = QComboBox()
        self.structure_dropdown.addItems(["Shot Date", "Import Date"])
        
        self.metadata_toggle = QCheckBox("Apply custom metadata")
        self.metadata_toggle.toggled.connect(self.metadata_panel.setVisible)

        self.open_dest_checkbox = QCheckBox("Open destination folder after import")
        self.open_dest_checkbox.setToolTip("If checked, the primary destination folder will open automatically when the import finishes.")

        self.import_button = QPushButton("Start Import")
        self.import_button.setStyleSheet("font-weight: bold; padding: 8px;")
        self.import_button.clicked.connect(self.start_import)
        
        self.close_button = QPushButton("Close Application")
        self.close_button.setStyleSheet("padding: 8px;")
        self.close_button.clicked.connect(self.close)
        self.close_button.setVisible(False)
        
        self.progress = QProgressBar()
        self.status_label = QLabel("Idle. Select source and destination to begin.")
        self.status_label.setWordWrap(True)

        self.import_layout.addWidget(source_group_label)
        self.import_layout.addLayout(source_button_layout)
        self.import_layout.addWidget(self.source_path_label)
        self.import_layout.addSpacing(15)
        self.import_layout.addWidget(dest_label)
        self.import_layout.addWidget(self.dest_button)
        self.import_layout.addWidget(self.dest_path_label)
        self.import_layout.addWidget(self.backup_button)
        self.import_layout.addWidget(self.backup_path_label)
        self.import_layout.addSpacing(20)
        self.import_layout.addWidget(self.structure_label)
        self.import_layout.addWidget(self.structure_dropdown)
        self.import_layout.addWidget(date_format_label)
        self.import_layout.addWidget(self.date_format_combo)
        self.import_layout.addSpacing(10)
        self.import_layout.addWidget(self.metadata_toggle)
        self.import_layout.addWidget(self.open_dest_checkbox)
        self.import_layout.addStretch()
        self.import_layout.addWidget(self.import_button)
        self.import_layout.addWidget(self.close_button)
        self.import_layout.addWidget(self.status_label)
        self.import_layout.addWidget(self.progress)
    
    def _create_menu_bar(self):
        """Creates the main window's menu bar."""
        menu_bar = self.menuBar()
        help_menu = menu_bar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _show_about_dialog(self):
        """Displays the 'About' message box."""
        QMessageBox.about(
            self,
            "About Photo Import & Tagger",
            f"""
            <b>Photo Import & Tagger</b>
            <p>Version: {APP_VERSION}</p>
            <p>A utility for importing photos with reliable backups and powerful,
            preset-driven metadata tagging.</p>
            <p>This tool helps photographers using manual lenses to embed
            critical EXIF data directly into their workflow.</p>
            """
        )

    def select_source_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Image Files", self.source_folder, "Images (*.jpg *.jpeg *.png *.cr2 *.nef *.arw *.dng *.rw2)")
        if files:
            self.selected_files = files
            self.source_folder = os.path.dirname(files[0])
            self.source_path_label.setText(f"{len(files)} file(s) selected")
            self.source_path_label.setToolTip("\n".join(files))
            self.source_path_label.setStyleSheet(NORMAL_STYLE)

    def select_source_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", self.source_folder)
        if folder:
            self.source_folder = folder
            self.selected_files = []
            self.source_path_label.setText(f"Folder: {truncate_path(folder)}")
            self.source_path_label.setToolTip(folder)
            self.source_path_label.setStyleSheet(NORMAL_STYLE)

    def select_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Primary Destination Folder", self.dest_folder)
        if folder:
            self.dest_folder = folder
            self.dest_path_label.setText(f"Primary: {truncate_path(folder)}")
            self.dest_path_label.setToolTip(folder)
            self.dest_path_label.setStyleSheet(NORMAL_STYLE)

    def select_backup(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder", self.backup_folder)
        if folder:
            self.backup_folder = folder
            self.backup_path_label.setText(f"Backup: {truncate_path(folder)}")
            self.backup_path_label.setToolTip(folder)
    
    def _validate_paths(self):
        """Checks for required paths and updates UI with error styles."""
        is_valid = True
        if not self.selected_files and not self.source_folder:
            self.source_path_label.setText("Error: A source must be selected.")
            self.source_path_label.setStyleSheet(ERROR_STYLE)
            is_valid = False
        
        if not self.dest_folder:
            self.dest_path_label.setText("Error: A primary destination must be selected.")
            self.dest_path_label.setStyleSheet(ERROR_STYLE)
            is_valid = False
        
        return is_valid

    def start_import(self):
        if not self._validate_paths():
            return
        
        try:
            file_count = len(self.selected_files) if self.selected_files else len([f for f in os.listdir(self.source_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.cr2', '.nef', '.arw', '.dng', '.rw2'))])
        except FileNotFoundError:
             QMessageBox.critical(self, "Error", f"Source folder not found: {self.source_folder}")
             return
        if file_count == 0:
            QMessageBox.information(self, "No Files Found", "The selected source contains no compatible image files.")
            return

        source_text = f"{file_count} file(s)" if self.selected_files else f"Folder: {truncate_path(self.source_folder)}"
        dest_text = truncate_path(self.dest_folder)
        backup_text = truncate_path(self.backup_folder) if self.backup_folder else "None"
        msg = (f"You are about to import:\n\nSource: {source_text}\nPrimary Destination: {dest_text}\nBackup Destination: {backup_text}\n\nProceed?")
        reply = QMessageBox.question(self, 'Confirm Import', msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.No:
            self.status_label.setText("Import cancelled by user.")
            return

        self.import_button.setVisible(False)
        self.close_button.setVisible(False)
        self.progress.setValue(0)
        user_format = self.date_format_combo.currentText()
        python_format = user_format.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
        current_metadata = self.metadata_panel.get_active_metadata() if self.metadata_toggle.isChecked() else {}
        self.import_worker = ImportWorker(
            source_folder=self.source_folder, source_files=self.selected_files, dest_folder=self.dest_folder,
            backup_folder=self.backup_folder, structure=self.structure_dropdown.currentText(), date_format=python_format,
            metadata=current_metadata)
        self.import_thread = QThread()
        self.import_worker.moveToThread(self.import_thread)
        self.import_thread.started.connect(self.import_worker.run)
        self.import_worker.progress.connect(self.progress.setValue)
        self.import_worker.status.connect(self.status_label.setText)
        self.import_worker.finished.connect(self.on_import_finished)
        self.import_thread.start()
        
    def on_import_finished(self):
        """Cleans up thread and handles post-import actions."""
        if self.import_thread:
            self.import_thread.quit()
            self.import_thread.wait()
        self.import_thread = None
        self.import_worker = None
        
        self.close_button.setVisible(True)
        self.import_button.setVisible(True)
        self.status_label.setText("Import complete. Ready to close or start another import.")

        if self.open_dest_checkbox.isChecked():
            if self.dest_folder and os.path.isdir(self.dest_folder):
                try:
                    open_folder(self.dest_folder)
                except Exception as e:
                    self.status_label.setText(f"Import complete, but failed to open folder: {e}")
        
    def load_settings(self):
        """Loads all saved settings and applies them to the UI."""
        self.date_format_combo.setCurrentText(self.settings.value("dateFormat", "YYYY-MM-DD"))
        self.open_dest_checkbox.setChecked(self.settings.value("openDestAfterImport", False, type=bool))
        
        last_source = self.settings.value("lastSourcePath", "")
        if last_source and os.path.isdir(last_source):
            self.source_folder = last_source
            self.source_path_label.setText(f"Folder: {truncate_path(last_source)}")
            self.source_path_label.setToolTip(last_source)
            self.source_path_label.setStyleSheet(NORMAL_STYLE)

        last_dest = self.settings.value("lastDestPath", "")
        if last_dest and os.path.isdir(last_dest):
            self.dest_folder = last_dest
            self.dest_path_label.setText(f"Primary: {truncate_path(last_dest)}")
            self.dest_path_label.setToolTip(last_dest)
            self.dest_path_label.setStyleSheet(NORMAL_STYLE)
            
        last_backup = self.settings.value("lastBackupPath", "")
        if last_backup and os.path.isdir(last_backup):
            self.backup_folder = last_backup
            self.backup_path_label.setText(f"Backup: {truncate_path(last_backup)}")
            self.backup_path_label.setToolTip(last_backup)

    def save_settings(self):
        """Saves current settings to the config file."""
        self.settings.setValue("dateFormat", self.date_format_combo.currentText())
        self.settings.setValue("openDestAfterImport", self.open_dest_checkbox.isChecked())
        self.settings.setValue("lastSourcePath", self.source_folder)
        self.settings.setValue("lastDestPath", self.dest_folder)
        self.settings.setValue("lastBackupPath", self.backup_folder)

    def closeEvent(self, event):
        """Saves settings and ensures the worker thread is stopped gracefully."""
        self.save_settings()
        if self.import_worker: self.import_worker.stop()
        if self.import_thread:
            self.import_thread.quit()
            self.import_thread.wait()
        event.accept()

# --- APPLICATION ENTRY POINT ---

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    if not exiftool_manager.check_or_install_exiftool():
        QMessageBox.critical(None, "Critical Error", "Could not install or find ExifTool. The application cannot continue.\n\nPlease check your internet connection or place 'exiftool.exe' and 'exiftool_files' in the 'resources' folder.")
        sys.exit(1)

    importer = ImageImporter()
    importer.show()
    sys.exit(app.exec())
