from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QComboBox, QHBoxLayout,
    QProgressBar, QCheckBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout
)
from PyQt6.QtCore import QThread
from import_worker import ImportWorker
from utils import truncate_path
from metadata_panel import MetadataPanel

class ImageImporter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Import Tool")
        self.setGeometry(100, 100, 900, 600)
        self.layout = QHBoxLayout(self)

        self.source_folder = ""
        self.selected_files = []
        self.dest_folder = ""
        self.backup_folder = ""

        self.build_import_form()
        self.build_metadata_panel()
        self.layout.addWidget(self.importForm)
        self.layout.addWidget(self.metadata_panel)

    def build_import_form(self):
        self.importForm = QWidget()
        self.importLayout = QVBoxLayout()
        self.importForm.setLayout(self.importLayout)

        self.source_label = QLabel("Select source folder (e.g., SD card):")
        self.source_button = QPushButton("Browse Source")
        self.source_path_label = QLabel("No folder selected")
        self.source_path_label.setStyleSheet("color: gray; font-style: italic")
        self.source_button.clicked.connect(self.select_source)

        self.dest_label = QLabel("Select destination folder:")
        self.dest_button = QPushButton("Browse Destination")
        self.dest_path_label = QLabel("No folder selected")
        self.dest_path_label.setStyleSheet("color: gray; font-style: italic")
        self.dest_button.clicked.connect(self.select_destination)

        self.backup_label = QLabel("Select backup folder (optional):")
        self.backup_button = QPushButton("Browse Backup")
        self.backup_button.clicked.connect(self.select_backup)

        self.structure_label = QLabel("Organize imports by:")
        self.structure_dropdown = QComboBox()
        self.structure_dropdown.addItems(["Import Date", "Shot Date"])

        self.metadata_label = QLabel("Add custom/advanced metadata?")
        self.metadata_dropdown = QComboBox()
        self.metadata_dropdown.addItems(["No", "Yes"])
        self.metadata_dropdown.currentTextChanged.connect(self.toggle_metadata_panel)

        self.import_button = QPushButton("Start Import")
        self.import_button.clicked.connect(self.start_import)

        self.progress = QProgressBar()
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("color: #666;")

        self.importLayout.addWidget(self.source_label)
        self.importLayout.addWidget(self.source_button)
        self.importLayout.addWidget(self.source_path_label)
        self.importLayout.addWidget(self.dest_label)
        self.importLayout.addWidget(self.dest_button)
        self.importLayout.addWidget(self.dest_path_label)
        self.importLayout.addWidget(self.backup_label)
        self.importLayout.addWidget(self.backup_button)
        self.importLayout.addWidget(self.structure_label)
        self.importLayout.addWidget(self.structure_dropdown)
        self.importLayout.addWidget(self.metadata_label)
        self.importLayout.addWidget(self.metadata_dropdown)
        self.importLayout.addWidget(self.import_button)
        self.importLayout.addWidget(self.status_label)
        self.importLayout.addWidget(self.progress)

    def build_metadata_panel(self):
        self.metadata_panel = MetadataPanel()
        self.metadata_panel.setVisible(False)

    def toggle_metadata_panel(self, text):
        self.metadata_panel.setVisible(text == "Yes")

    def select_source(self):
        choice, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files or Cancel to Choose a Folder",
            "",
            "Images (*.jpg *.jpeg *.png *.cr2 *.nef *.arw *.dng)"
        )
        if choice:
            self.selected_files = choice
            self.source_folder = ""  # Clear folder if files selected
            self.source_path_label.setText(f"{len(choice)} file(s) selected")
            self.source_path_label.setToolTip("\n".join(choice))
        else:
            folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
            if folder:
                self.source_folder = folder
                self.selected_files = []  # Clear files if folder selected
                display_path = truncate_path(folder)
                self.source_path_label.setText(display_path)
                self.source_path_label.setToolTip(folder)

    def select_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.dest_folder = folder
            display_path = truncate_path(folder)
            self.dest_path_label.setText(display_path)
            self.dest_path_label.setToolTip(folder)

    def select_backup(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder (Optional)")
        if folder:
            self.backup_folder = folder

    def start_import(self):
        if not (self.selected_files or self.source_folder) or not self.dest_folder:
            self.status_label.setText("Error: Select source (folder or files) and destination.")
            return

        self.import_button.setEnabled(False)
        self.progress.setValue(0)
        self.status_label.setText("Starting import...")

        metadata = self.metadata_panel.get_metadata() if self.metadata_dropdown.currentText() == "Yes" else {}

        self.worker = ImportWorker(
            source_folder=self.source_folder,
            source_files=self.selected_files,
            dest_folder=self.dest_folder,
            backup_folder=self.backup_folder,
            structure=self.structure_dropdown.currentText(),
            metadata=metadata
        )
        self.thread = QThread()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: self.import_button.setEnabled(True))

        self.thread.start()