import sys
import shutil
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QHBoxLayout, QProgressBar, QCheckBox,
    QLineEdit, QTextEdit, QGroupBox, QGridLayout, QSpacerItem,
    QSizePolicy
)
from PyQt6.QtCore import Qt


class ImageImporter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Import Tool")
        self.setGeometry(100, 100, 900, 600)

        self.layout = QHBoxLayout(self)

        # LEFT PANEL — MAIN IMPORT FORM
        self.importForm = QWidget()
        self.importLayout = QVBoxLayout()
        self.importForm.setLayout(self.importLayout)

        # Source folder selection
        source_layout = QVBoxLayout()
        source_button = QPushButton("Browse Source")
        self.source_path_label = QLabel("No folder selected")
        self.source_path_label.setStyleSheet("color: gray; font-style: italic")
        source_layout.addWidget(source_button)
        source_layout.addWidget(self.source_path_label)
        source_button.clicked.connect(self.select_source)

        # Destination folder selection
        dest_layout = QVBoxLayout()
        dest_button = QPushButton("Browse Destination")
        self.dest_path_label = QLabel("No folder selected")
        self.dest_path_label.setStyleSheet("color: gray; font-style: italic")
        dest_layout.addWidget(dest_button)
        dest_layout.addWidget(self.dest_path_label)
        dest_button.clicked.connect(self.select_destination)

        # Import structure
        self.structure_label = QLabel("Organize imports by:")
        self.structure_dropdown = QComboBox()
        self.structure_dropdown.addItems(["Import Date", "Shot Date"])

        # Metadata screening question
        self.metadata_label = QLabel("Add custom/advanced metadata?")
        self.metadata_dropdown = QComboBox()
        self.metadata_dropdown.addItems(["No", "Yes"])
        self.metadata_dropdown.currentTextChanged.connect(self.toggle_metadata_panel)

        # Import button and progress
        self.import_button = QPushButton("Start Import")
        self.import_button.clicked.connect(self.start_import)
        self.progress = QProgressBar()

        self.importLayout.addWidget(self.source_label)
        self.importLayout.addWidget(self.source_button)
        self.importLayout.addWidget(self.dest_label)
        self.importLayout.addWidget(self.dest_button)
        self.importLayout.addWidget(self.backup_label)
        self.importLayout.addWidget(self.backup_button)
        self.importLayout.addWidget(self.structure_label)
        self.importLayout.addWidget(self.structure_dropdown)
        self.importLayout.addWidget(self.metadata_label)
        self.importLayout.addWidget(self.metadata_dropdown)
        self.importLayout.addWidget(self.import_button)
        self.importLayout.addWidget(self.progress)

        self.layout.addWidget(self.importForm)

        # RIGHT PANEL — METADATA PANEL (Initially Hidden)
        self.metadata_panel = QGroupBox("Metadata Entry")
        self.metadata_layout = QGridLayout()
        self.metadata_panel.setLayout(self.metadata_layout)

        # Global fields
        self.make_input = QLineEdit()
        self.model_input = QLineEdit()
        self.metadata_layout.addWidget(QLabel("Lens Make:"), 0, 0)
        self.metadata_layout.addWidget(self.make_input, 0, 1)
        self.metadata_layout.addWidget(QLabel("Lens Model:"), 1, 0)
        self.metadata_layout.addWidget(self.model_input, 1, 1)

        # Optional checkbox-controlled fields
        self.focal_checkbox = QCheckBox("Add Focal Length")
        self.focal_input = QLineEdit()
        self.focal_input.setPlaceholderText("e.g., 85mm")
        self.focal_input.setEnabled(False)

        self.aperture_checkbox = QCheckBox("Add Aperture")
        self.aperture_input = QLineEdit()
        self.aperture_input.setPlaceholderText("e.g., 2.8")
        self.aperture_input.setEnabled(False)

        self.serial_checkbox = QCheckBox("Add Lens Serial")
        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("Optional")
        self.serial_input.setEnabled(False)

        self.notes_checkbox = QCheckBox("Add Notes")
        self.notes_input = QTextEdit()
        self.notes_input.setEnabled(False)

        self.focal_checkbox.stateChanged.connect(lambda: self.focal_input.setEnabled(self.focal_checkbox.isChecked()))
        self.aperture_checkbox.stateChanged.connect(lambda: self.aperture_input.setEnabled(self.aperture_checkbox.isChecked()))
        self.serial_checkbox.stateChanged.connect(lambda: self.serial_input.setEnabled(self.serial_checkbox.isChecked()))
        self.notes_checkbox.stateChanged.connect(lambda: self.notes_input.setEnabled(self.notes_checkbox.isChecked()))

        self.metadata_layout.addWidget(self.focal_checkbox, 2, 0)
        self.metadata_layout.addWidget(self.focal_input, 2, 1)
        self.metadata_layout.addWidget(self.aperture_checkbox, 3, 0)
        self.metadata_layout.addWidget(self.aperture_input, 3, 1)
        self.metadata_layout.addWidget(self.serial_checkbox, 4, 0)
        self.metadata_layout.addWidget(self.serial_input, 4, 1)
        self.metadata_layout.addWidget(self.notes_checkbox, 5, 0)
        self.metadata_layout.addWidget(self.notes_input, 5, 1, 2, 1)

        self.metadata_panel.setVisible(False)
        self.layout.addWidget(self.metadata_panel)

        # Internal vars
        self.source_folder = ""
        self.dest_folder = ""
        self.backup_folder = ""

    def select_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            self.source_folder = folder
            display_path = self.truncate_path(folder)
            self.source_path_label.setText(display_path)
            self.source_path_label.setToolTip(folder)

    def select_destination(self):  # ← THIS is what you need to add
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.dest_folder = folder
            display_path = self.truncate_path(folder)
            self.dest_path_label.setText(display_path)
            self.dest_path_label.setToolTip(folder)
        
    def truncate_path(self, path, max_len=50):
        return path if len(path) <= max_len else f"...{path[-(max_len - 3):]}"        

    def select_backup(self):
        self.backup_folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder (Optional)")

    def toggle_metadata_panel(self, text):
        self.metadata_panel.setVisible(text == "Yes")

    def start_import(self):
        if not self.source_folder or not self.dest_folder:
            print("Source and destination folders must be selected.")
            return

        files = [f for f in os.listdir(self.source_folder) if os.path.isfile(os.path.join(self.source_folder, f))]
        total = len(files)
        if total == 0:
            print("No files to import.")
            return

        self.progress.setValue(0)
        for i, file in enumerate(files):
            src = os.path.join(self.source_folder, file)

            if self.structure_dropdown.currentText() == "Shot Date":
                timestamp = os.path.getmtime(src)
            else:
                timestamp = os.path.getctime(src)

            date_str = self.format_date(timestamp)
            dest_subfolder = os.path.join(self.dest_folder, date_str)
            os.makedirs(dest_subfolder, exist_ok=True)
            dest = os.path.join(dest_subfolder, file)
            shutil.copy2(src, dest)

            if self.backup_folder:
                backup_subfolder = os.path.join(self.backup_folder, date_str)
                os.makedirs(backup_subfolder, exist_ok=True)
                shutil.copy2(src, os.path.join(backup_subfolder, file))

            pct = int((i + 1) / total * 100)
            self.progress.setValue(pct)

    def format_date(self, timestamp):
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    importer = ImageImporter()
    importer.show()
    sys.exit(app.exec())
