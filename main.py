import sys
import os
import shutil
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QProgressBar, QHBoxLayout
)


class ImportWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Importer")
        self.setGeometry(200, 200, 500, 350)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Source folder
        self.source_label = QLabel("Source Folder (Camera/SD Card):")
        self.source_button = QPushButton("Choose Folder")
        self.source_button.clicked.connect(self.choose_source_folder)
        layout.addWidget(self.source_label)
        layout.addWidget(self.source_button)

        # Primary folder
        self.primary_label = QLabel("Primary Save Location:")
        self.primary_button = QPushButton("Choose Folder")
        self.primary_button.clicked.connect(self.choose_primary_folder)
        layout.addWidget(self.primary_label)
        layout.addWidget(self.primary_button)

        # Backup folder
        self.backup_label = QLabel("Backup Save Location (Optional):")
        self.backup_button = QPushButton("Choose Folder")
        self.backup_button.clicked.connect(self.choose_backup_folder)
        layout.addWidget(self.backup_label)
        layout.addWidget(self.backup_button)

        # Folder structure choice
        self.structure_label = QLabel("Folder Structure:")
        self.structure_dropdown = QComboBox()
        self.structure_dropdown.addItems(["By Import Date", "By Shot Date"])
        layout.addWidget(self.structure_label)
        layout.addWidget(self.structure_dropdown)

        # Screening question
        self.metadata_label = QLabel("Add custom/advanced metadata?")
        self.metadata_dropdown = QComboBox()
        self.metadata_dropdown.addItems(["No", "Yes"])
        layout.addWidget(self.metadata_label)
        layout.addWidget(self.metadata_dropdown)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Import button
        self.import_button = QPushButton("Start Import")
        self.import_button.clicked.connect(self.start_import)
        layout.addWidget(self.import_button)

        self.setLayout(layout)

    def choose_source_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            self.source_label.setText(f"Source Folder: {folder}")
            self.source_path = folder

    def choose_primary_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Primary Folder")
        if folder:
            self.primary_label.setText(f"Primary Save Location: {folder}")
            self.primary_path = folder

    def choose_backup_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder (Optional)")
        if folder:
            self.backup_label.setText(f"Backup Save Location: {folder}")
            self.backup_path = folder

    def start_import(self):
        if not hasattr(self, 'source_path') or not hasattr(self, 'primary_path'):
            print("Missing source or primary path.")
            return

        import_now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        structure = self.structure_dropdown.currentText()

        # Gather files
        all_files = []
        for root, dirs, files in os.walk(self.source_path):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.cr2', '.nef', '.arw', '.raf', '.dng', '.rw2')):
                    all_files.append(os.path.join(root, file))

        total_files = len(all_files)
        if total_files == 0:
            print("No supported image files found.")
            return

        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)

        for idx, src_file in enumerate(all_files, start=1):
            # Determine subfolder name
            if structure == "By Import Date":
                subfolder = import_now
            else:
                try:
                    mtime = os.path.getmtime(src_file)
                    shot_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                    subfolder = shot_date
                except Exception:
                    subfolder = "unknown_date"

            # Copy to primary
            dest_primary = os.path.join(self.primary_path, subfolder)
            os.makedirs(dest_primary, exist_ok=True)
            shutil.copy2(src_file, dest_primary)

            # Copy to backup if available
            if hasattr(self, 'backup_path'):
                dest_backup = os.path.join(self.backup_path, subfolder)
                os.makedirs(dest_backup, exist_ok=True)
                shutil.copy2(src_file, dest_backup)

            # Update progress
            percent = int((idx / total_files) * 100)
            self.progress_bar.setValue(idx)
            self.progress_bar.setFormat(f"{idx}/{total_files} files ({percent}%)")

        print("Import completed.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImportWindow()
    window.show()
    sys.exit(app.exec())
