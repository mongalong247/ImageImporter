import sys
import os
import shutil
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QComboBox, QHBoxLayout,
    QProgressBar, QCheckBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, QApplication, QMessageBox
)
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QSettings

# New: Import the dedicated manager for all ExifTool operations.
import exiftool_manager

# --- UTILITY FUNCTIONS ---

def truncate_path(path: str, max_len: int = 60) -> str:
    """Truncates a long path for display."""
    return path if len(path) <= max_len else f"...{path[-(max_len - 3):]}"

# --- GUI: METADATA PANEL ---

class MetadataPanel(QGroupBox):
    """A QGroupBox for entering custom metadata."""
    def __init__(self):
        super().__init__("Metadata to Apply")
        # (Layout and widget definitions remain unchanged)
        self.layout = QGridLayout(self)
        self.make_input = QLineEdit()
        self.model_input = QLineEdit()
        self.focal_input = QLineEdit()
        self.focal_input.setPlaceholderText("e.g., 85 or 85mm")
        self.aperture_input = QLineEdit()
        self.aperture_input.setPlaceholderText("e.g., 2.8 or f/2.8")
        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("Optional lens serial number")
        self.notes_input = QTextEdit()
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
        """Collects data from the input fields."""
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
    """Handles the file import process in a background thread."""
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
        """The main logic for the import process."""
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
                    # Update: Call the modular function
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
                    # Update: Call the modular function
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

class ImageImporter(QWidget):
    """The main application window."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photo Import & Tagger")
        self.setGeometry(100, 100, 900, 600)
        self.settings = QSettings("MyCompany", "ImageImporter")
        
        self.layout = QHBoxLayout(self)
        self.source_folder = ""
        self.selected_files = []
        self.dest_folder = ""
        self.backup_folder = ""
        self.import_thread = None
        self.import_worker = None

        self.metadata_panel = MetadataPanel()
        self.build_import_form()
        
        self.layout.addWidget(self.import_form_group)
        self.layout.addWidget(self.metadata_panel)
        self.metadata_panel.setVisible(False)

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
        self.source_path_label.setStyleSheet("color: gray; font-style: italic;")

        dest_label = QLabel("2. Choose Destinations:")
        self.dest_button = QPushButton("Primary Destination...")
        self.dest_button.clicked.connect(self.select_destination)
        self.dest_path_label = QLabel("No destination selected")
        self.dest_path_label.setStyleSheet("color: gray; font-style: italic;")
        self.backup_button = QPushButton("Backup Destination... (Optional)")
        self.backup_button.clicked.connect(self.select_backup)
        self.backup_path_label = QLabel("No backup folder selected")
        self.backup_path_label.setStyleSheet("color: gray; font-style: italic;")
        
        date_format_label = QLabel("Folder Date Format:")
        self.date_format_combo = QComboBox()
        self.date_format_combo.setEditable(True)
        date_formats = ["YYYY-MM-DD", "YYYYMMDD", "YYYY-MM", "YYYY/MM-DD"]
        self.date_format_combo.addItems(date_formats)
        self.date_format_combo.setToolTip("Use YYYY, MM, DD to define folder names.\nExample: 'Photos/YYYY/MM' will be converted to Python's strftime format.")
        saved_format = self.settings.value("dateFormat", "YYYY-MM-DD")
        self.date_format_combo.setCurrentText(saved_format)

        self.structure_label = QLabel("Organize subfolders by:")
        self.structure_dropdown = QComboBox()
        self.structure_dropdown.addItems(["Shot Date", "Import Date"])
        self.metadata_toggle = QCheckBox("Apply custom metadata")
        self.metadata_toggle.toggled.connect(self.metadata_panel.setVisible)

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
        self.import_layout.addStretch()
        self.import_layout.addWidget(self.import_button)
        self.import_layout.addWidget(self.close_button)
        self.import_layout.addWidget(self.status_label)
        self.import_layout.addWidget(self.progress)
    
    def select_source_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Image Files", "", "Images (*.jpg *.jpeg *.png *.cr2 *.nef *.arw *.dng *.rw2)")
        if files:
            self.selected_files = files
            self.source_folder = ""
            self.source_path_label.setText(f"{len(files)} file(s) selected")
            self.source_path_label.setToolTip("\n".join(files))

    def select_source_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            self.source_folder = folder
            self.selected_files = []
            self.source_path_label.setText(f"Folder: {truncate_path(folder)}")
            self.source_path_label.setToolTip(folder)

    def select_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Primary Destination Folder")
        if folder:
            self.dest_folder = folder
            self.dest_path_label.setText(f"Primary: {truncate_path(folder)}")
            self.dest_path_label.setToolTip(folder)

    def select_backup(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
        if folder:
            self.backup_folder = folder
            self.backup_path_label.setText(f"Backup: {truncate_path(folder)}")
            self.backup_path_label.setToolTip(folder)
    
    def start_import(self):
        if not (self.selected_files or self.source_folder) or not self.dest_folder:
            QMessageBox.warning(self, "Missing Information", "A source (files or a folder) and a primary destination must be selected.")
            return
        
        file_count = len(self.selected_files) if self.selected_files else len([f for f in os.listdir(self.source_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.cr2', '.nef', '.arw', '.dng', '.rw2'))])
        if file_count == 0:
            QMessageBox.information(self, "No Files Found", "The selected source contains no compatible image files.")
            return

        source_text = f"{file_count} file(s)" if self.selected_files else f"Folder: {truncate_path(self.source_folder)}"
        dest_text = truncate_path(self.dest_folder)
        backup_text = truncate_path(self.backup_folder) if self.backup_folder else "None"
        
        msg = (f"You are about to import:\n\n"
               f"Source: {source_text}\n"
               f"Primary Destination: {dest_text}\n"
               f"Backup Destination: {backup_text}\n\n"
               f"Proceed with the import?")

        reply = QMessageBox.question(self, 'Confirm Import', msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.No:
            self.status_label.setText("Import cancelled by user.")
            return

        self.import_button.setVisible(False)
        self.close_button.setVisible(False)
        self.progress.setValue(0)
        
        user_format = self.date_format_combo.currentText()
        python_format = user_format.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")

        self.import_worker = ImportWorker(
            source_folder=self.source_folder,
            source_files=self.selected_files,
            dest_folder=self.dest_folder,
            backup_folder=self.backup_folder,
            structure=self.structure_dropdown.currentText(),
            date_format=python_format,
            metadata=self.metadata_panel.get_metadata() if self.metadata_toggle.isChecked() else {}
        )
        self.import_thread = QThread()
        self.import_worker.moveToThread(self.import_thread)
        self.import_thread.started.connect(self.import_worker.run)
        self.import_worker.progress.connect(self.progress.setValue)
        self.import_worker.status.connect(self.status_label.setText)
        self.import_worker.finished.connect(self.on_import_finished)
        self.import_thread.start()
        
    def on_import_finished(self):
        """Cleans up the thread and shows the post-import buttons."""
        self.import_thread.quit()
        self.import_thread.wait()
        self.import_thread = None
        self.import_worker = None
        
        self.close_button.setVisible(True)
        self.import_button.setVisible(True)
        self.status_label.setText("Import complete. Ready to close or start another import.")
        
    def closeEvent(self, event):
        """Saves settings and ensures the worker thread is stopped gracefully."""
        self.settings.setValue("dateFormat", self.date_format_combo.currentText())
        if self.import_worker: self.import_worker.stop()
        if self.import_thread:
            self.import_thread.quit()
            self.import_thread.wait()
        event.accept()

# --- APPLICATION ENTRY POINT ---

if __name__ == "__main__":
    # Update: Call the modular function to check for ExifTool.
    if not exiftool_manager.check_or_install_exiftool():
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Critical Error", "Could not install or find ExifTool. The application cannot continue.\n\nPlease check your internet connection or place 'exiftool.exe' in the 'resources' folder.")
        sys.exit(1)

    app = QApplication(sys.argv)
    importer = ImageImporter()
    importer.show()
    sys.exit(app.exec())
