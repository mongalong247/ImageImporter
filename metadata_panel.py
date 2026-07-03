import sys
import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox, QHBoxLayout,
    QLineEdit, QTextEdit, QGroupBox, QGridLayout, QApplication, QMessageBox,
    QTabWidget, QFileDialog, QDialog
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

import paths
import qr_codes

# Resolved centrally in paths.py so this always agrees with exiftool_manager
# and app.py on where the persistent resources folder actually is, even in
# a PyInstaller-frozen build.
RESOURCES_DIR = paths.RESOURCES_DIR
PRESETS_FILE_PATH = os.path.join(RESOURCES_DIR, "lens_presets.json")

class MetadataManagerPanel(QWidget):
    """
    A comprehensive widget for managing and applying metadata, including a
    tab-based interface for manual entry and saved lens presets.
    """
    def __init__(self):
        super().__init__()
        self.presets = {}  # In-memory dictionary to hold loaded presets

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # --- Create Tabs (Presets tab is now first) ---
        self._create_presets_management_tab()
        self._create_active_metadata_tab()

        # --- Final Setup ---
        self._load_presets_from_file() # Load presets and populate the UI

    def get_active_metadata(self) -> dict:
        """
        Public method to get the metadata currently entered in the 'Active' tab.
        This is the single source of truth for the import process.
        """
        return {
            "LensMake": self.make_input.text().strip(),
            "LensModel": self.model_input.text().strip(),
            "FocalLength": self.focal_input.text().strip(),
            "FNumber": self.aperture_input.text().strip(),
            "LensSerialNumber": self.serial_input.text().strip(),
            "ImageDescription": self.notes_input.toPlainText().strip()
        }

    # --- UI Creation Methods ---

    def _create_active_metadata_tab(self):
        """Creates the second tab for manually entering the metadata to be applied."""
        self.active_metadata_tab = QWidget()
        layout = QGridLayout(self.active_metadata_tab)
        
        # This group box contains all the fields for the currently active metadata
        group_box = QGroupBox("Metadata to be Applied on Next Import")
        grid = QGridLayout(group_box)

        # Create input fields
        self.make_input = QLineEdit()
        self.model_input = QLineEdit()
        self.focal_input = QLineEdit()
        self.focal_input.setPlaceholderText("e.g., 85 or 85mm")
        self.aperture_input = QLineEdit()
        self.aperture_input.setPlaceholderText("e.g., 2.8 or f/2.8")
        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("Optional lens serial number")
        self.notes_input = QTextEdit()
        
        # Add widgets to the grid
        grid.addWidget(QLabel("Lens Make:"), 0, 0)
        grid.addWidget(self.make_input, 0, 1)
        grid.addWidget(QLabel("Lens Model:"), 1, 0)
        grid.addWidget(self.model_input, 1, 1)
        grid.addWidget(QLabel("Focal Length:"), 2, 0)
        grid.addWidget(self.focal_input, 2, 1)
        grid.addWidget(QLabel("Aperture (F-Number):"), 3, 0)
        grid.addWidget(self.aperture_input, 3, 1)
        grid.addWidget(QLabel("Lens Serial:"), 4, 0)
        grid.addWidget(self.serial_input, 4, 1)
        grid.addWidget(QLabel("Notes/Description:"), 5, 0)
        grid.addWidget(self.notes_input, 5, 1, 1, 1)
        
        layout.addWidget(group_box)
        self.tab_widget.addTab(self.active_metadata_tab, "Active Metadata")

    def _create_presets_management_tab(self):
        """Creates the first tab for loading, saving, and deleting presets."""
        self.presets_tab = QWidget()
        layout = QVBoxLayout(self.presets_tab)
        
        # --- Load/Delete Group ---
        load_group = QGroupBox("Load or Delete a Saved Preset")
        load_layout = QVBoxLayout(load_group)

        load_layout.addWidget(QLabel("Saved Presets:"))
        self.presets_combo = QComboBox()
        self.presets_combo.setToolTip("Select a saved lens preset.")
        load_layout.addWidget(self.presets_combo)

        # Button layout for Load/Delete
        load_button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load to Active Tab")
        self.load_button.setToolTip("Copies the selected preset's data to the 'Active Metadata' tab.")
        self.load_button.clicked.connect(self._on_load_preset)

        self.delete_button = QPushButton("Delete Selected Preset")
        self.delete_button.setToolTip("Permanently deletes the selected preset.")
        self.delete_button.clicked.connect(self._on_delete_preset)

        self.generate_qr_button = QPushButton("Generate QR Code...")
        self.generate_qr_button.setToolTip(
            "Creates a printable QR code for the selected preset -- scan it as your "
            "first frame after changing lens or aperture."
        )
        self.generate_qr_button.clicked.connect(self._on_generate_qr)

        load_button_layout.addWidget(self.generate_qr_button)
        load_button_layout.addStretch(1) # Add stretch to push buttons to the right
        load_button_layout.addWidget(self.delete_button)
        load_button_layout.addWidget(self.load_button)
        load_layout.addLayout(load_button_layout)
        
        # --- Save Group ---
        save_group = QGroupBox("Save a New Preset from Active Metadata")
        save_layout = QVBoxLayout(save_group)

        save_layout.addWidget(QLabel("New Preset Name:"))
        self.preset_name_input = QLineEdit()
        self.preset_name_input.setPlaceholderText("e.g., Canon 50mm f/1.8")
        save_layout.addWidget(self.preset_name_input)
        
        self.save_button = QPushButton("Save Active Metadata")
        self.save_button.setToolTip("Saves the data from the 'Active Metadata' tab as a new preset.")
        self.save_button.clicked.connect(self._on_save_preset)
        
        # Button layout for Save
        save_button_layout = QHBoxLayout()
        save_button_layout.addStretch(1)
        save_button_layout.addWidget(self.save_button)
        save_layout.addLayout(save_button_layout)
        
        # --- Import/Export Group ---
        io_group = QGroupBox("Backup & Sharing")
        io_layout = QVBoxLayout(io_group)
        io_layout.addWidget(QLabel("Export all presets to a file, or import presets from one."))

        io_button_layout = QHBoxLayout()
        self.export_button = QPushButton("Export Presets...")
        self.export_button.setToolTip("Save all current presets to a .json file you can back up or share.")
        self.export_button.clicked.connect(self._on_export_presets)

        self.import_button = QPushButton("Import Presets...")
        self.import_button.setToolTip("Load presets from a previously exported .json file.")
        self.import_button.clicked.connect(self._on_import_presets)

        io_button_layout.addStretch(1)
        io_button_layout.addWidget(self.import_button)
        io_button_layout.addWidget(self.export_button)
        io_layout.addLayout(io_button_layout)
        
        layout.addWidget(load_group)
        layout.addWidget(save_group)
        layout.addWidget(io_group)
        layout.addStretch() # Pushes groups to the top
        self.tab_widget.addTab(self.presets_tab, "Lens Presets")

    # --- Preset Logic Methods ---

    def _load_presets_from_file(self):
        """Loads lens presets from the JSON file into memory and updates the UI."""
        try:
            os.makedirs(RESOURCES_DIR, exist_ok=True)
            if os.path.exists(PRESETS_FILE_PATH):
                with open(PRESETS_FILE_PATH, 'r') as f:
                    self.presets = json.load(f)
            else:
                self.presets = {}
        except (json.JSONDecodeError, IOError) as e:
            print(f"Could not load presets file: {e}")
            self.presets = {} # Reset to empty on error
        
        self._update_presets_combo()

    def _save_presets_to_file(self):
        """Saves the current in-memory presets to the JSON file."""
        try:
            os.makedirs(RESOURCES_DIR, exist_ok=True)
            with open(PRESETS_FILE_PATH, 'w') as f:
                json.dump(self.presets, f, indent=4)
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Could not save presets file:\n{e}")

    def _update_presets_combo(self):
        """Clears and repopulates the presets dropdown from the in-memory dictionary."""
        self.presets_combo.clear()
        sorted_presets = sorted(self.presets.keys())
        self.presets_combo.addItems(sorted_presets)

    # --- Signal Handlers (Slots) ---

    def _on_load_preset(self):
        """Handles the 'Load' button click."""
        preset_name = self.presets_combo.currentText()
        if not preset_name:
            QMessageBox.warning(self, "No Preset Selected", "Please select a preset from the list to load.")
            return

        preset_data = self.presets.get(preset_name)
        if preset_data:
            self.make_input.setText(preset_data.get("LensMake", ""))
            self.model_input.setText(preset_data.get("LensModel", ""))
            self.focal_input.setText(preset_data.get("FocalLength", ""))
            self.aperture_input.setText(preset_data.get("FNumber", ""))
            self.serial_input.setText(preset_data.get("LensSerialNumber", ""))
            self.notes_input.setPlainText(preset_data.get("ImageDescription", ""))
            
            # Switch to the active tab (now index 1) to show the loaded data
            self.tab_widget.setCurrentIndex(1)
            QMessageBox.information(self, "Preset Loaded", f"'{preset_name}' has been loaded into the 'Active Metadata' tab.")

    def _on_save_preset(self):
        """Handles the 'Save' button click."""
        preset_name = self.preset_name_input.text().strip()
        if not preset_name:
            QMessageBox.warning(self, "Missing Name", "Please enter a name for the new preset.")
            return

        if preset_name in self.presets:
            reply = QMessageBox.question(self, "Preset Exists", f"A preset named '{preset_name}' already exists. Overwrite it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

        # Get data from the active tab and save it
        active_data = self.get_active_metadata()
        self.presets[preset_name] = active_data
        self._save_presets_to_file()
        self._update_presets_combo()
        
        self.preset_name_input.clear() # Clear the input field
        QMessageBox.information(self, "Preset Saved", f"Preset '{preset_name}' has been saved successfully.")

    def _on_delete_preset(self):
        """Handles the 'Delete' button click."""
        preset_name = self.presets_combo.currentText()
        if not preset_name:
            QMessageBox.warning(self, "No Preset Selected", "Please select a preset from the list to delete.")
            return

        reply = QMessageBox.question(self, "Confirm Deletion", f"Are you sure you want to permanently delete the preset '{preset_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            if preset_name in self.presets:
                del self.presets[preset_name]
                self._save_presets_to_file()
                self._update_presets_combo()
                QMessageBox.information(self, "Preset Deleted", f"Preset '{preset_name}' has been deleted.")

    def _on_generate_qr(self):
        """Generates and previews a printable QR code for the selected saved preset."""
        preset_name = self.presets_combo.currentText()
        if not preset_name:
            QMessageBox.warning(self, "No Preset Selected", "Please select a saved preset to generate a QR code for.")
            return

        preset_data = self.presets.get(preset_name)
        if not preset_data:
            return

        try:
            qr_image = qr_codes.generate_preset_qr(preset_name, preset_data)
        except Exception as e:
            QMessageBox.critical(self, "QR Generation Failed", f"Could not generate a QR code:\n{e}")
            return

        dialog = QRCodePreviewDialog(qr_image, preset_name, self)
        dialog.exec()

    def _on_export_presets(self):
        """Exports all current presets to a user-chosen .json file."""
        if not self.presets:
            QMessageBox.information(self, "Nothing to Export", "There are no saved presets to export yet.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Presets", "lens_presets_export.json", "JSON Files (*.json)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".json"):
            file_path += ".json"

        try:
            with open(file_path, 'w') as f:
                json.dump(self.presets, f, indent=4)
            QMessageBox.information(self, "Export Complete", f"Exported {len(self.presets)} preset(s) to:\n{file_path}")
        except IOError as e:
            QMessageBox.critical(self, "Export Failed", f"Could not write to that file:\n{e}")

    @staticmethod
    def _is_valid_presets_structure(data) -> bool:
        """
        Validates that imported data has the expected shape: a dict mapping
        preset name (str) -> preset fields (dict). Rejects anything else so
        a malformed or hand-edited file can't corrupt the preset store or
        crash the panel later when it expects certain keys/types.
        """
        if not isinstance(data, dict):
            return False
        for name, preset_data in data.items():
            if not isinstance(name, str) or not isinstance(preset_data, dict):
                return False
        return True

    def _on_import_presets(self):
        """Imports presets from a user-chosen .json file, with conflict handling."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Presets", "", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, 'r') as f:
                imported_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.critical(self, "Import Failed", f"Could not read that file as valid JSON:\n{e}")
            return

        if not self._is_valid_presets_structure(imported_data):
            QMessageBox.critical(
                self, "Import Failed",
                "That file doesn't look like a valid presets export. Expected a JSON object "
                "mapping preset names to preset fields."
            )
            return

        if not imported_data:
            QMessageBox.information(self, "Nothing to Import", "That file doesn't contain any presets.")
            return

        conflicts = sorted(set(imported_data.keys()) & set(self.presets.keys()))
        overwrite_conflicts = True

        if conflicts:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Preset Conflicts")
            msg_box.setText(
                f"{len(conflicts)} preset(s) in this file have the same name as existing presets:\n\n"
                + ", ".join(conflicts)
                + "\n\nHow would you like to handle these?"
            )
            overwrite_btn = msg_box.addButton("Overwrite", QMessageBox.ButtonRole.AcceptRole)
            skip_btn = msg_box.addButton("Skip Conflicts", QMessageBox.ButtonRole.ActionRole)
            cancel_btn = msg_box.addButton("Cancel Import", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()
            clicked = msg_box.clickedButton()

            if clicked == cancel_btn:
                return
            overwrite_conflicts = (clicked == overwrite_btn)

        imported_count = 0
        skipped_count = 0
        for name, preset_data in imported_data.items():
            if name in self.presets and not overwrite_conflicts:
                skipped_count += 1
                continue
            self.presets[name] = preset_data
            imported_count += 1

        self._save_presets_to_file()
        self._update_presets_combo()

        summary = f"Imported {imported_count} preset(s)."
        if skipped_count:
            summary += f" Skipped {skipped_count} conflicting preset(s)."
        QMessageBox.information(self, "Import Complete", summary)


class QRCodePreviewDialog(QDialog):
    """
    Shows the generated QR code for a preset and lets the user save it as a
    PNG to print, or copy it to the clipboard. Kept intentionally simple for
    step 1 of the QR roadmap -- no batch/label-sheet printing yet, just one
    code at a time.
    """
    # The on-screen preview is scaled to fit within this square; the
    # full-resolution image (which can easily be 700px+ per side at this
    # error-correction level) is kept separately for saving/copying so
    # print quality isn't affected by the preview size.
    PREVIEW_MAX_SIZE = 420

    def __init__(self, qr_image, preset_name: str, parent=None):
        super().__init__(parent)
        self.qr_image = qr_image
        self.preset_name = preset_name
        self.setWindowTitle(f"QR Code - {preset_name}")
        self.setMinimumSize(360, 420)
        self.setMaximumSize(1000, 1000)
        self.resize(480, 560)

        layout = QVBoxLayout(self)

        self._full_pixmap = QPixmap()
        self._full_pixmap.loadFromData(qr_codes.qr_image_to_png_bytes(qr_image))

        preview_label = QLabel()
        preview_label.setPixmap(self._full_pixmap.scaled(
            self.PREVIEW_MAX_SIZE, self.PREVIEW_MAX_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(preview_label)

        size_label = QLabel(f"Full resolution: {qr_image.width}\u00d7{qr_image.height}px")
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(size_label)

        hint_label = QLabel(
            "Print this and place it inside your lens cap, or in a notebook. "
            "Scan it as your first frame after changing lens or aperture."
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(hint_label)
        layout.addStretch(1)

        button_layout = QHBoxLayout()
        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(self._on_copy)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        save_button = QPushButton("Save As PNG...")
        save_button.clicked.connect(self._on_save)
        button_layout.addWidget(copy_button)
        button_layout.addStretch(1)
        button_layout.addWidget(close_button)
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)

    def _on_copy(self):
        # Copies the full-resolution image, not the scaled-down preview,
        # so pasting elsewhere doesn't lose print quality.
        QApplication.clipboard().setPixmap(self._full_pixmap)
        QMessageBox.information(self, "Copied", "QR code copied to clipboard (full resolution).")

    def _on_save(self):
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in self.preset_name).strip()
        default_name = f"{safe_name or 'lens_preset'}_qr.png"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save QR Code", default_name, "PNG Images (*.png)")
        if not file_path:
            return
        if not file_path.lower().endswith(".png"):
            file_path += ".png"
        try:
            self.qr_image.save(file_path)
            QMessageBox.information(self, "Saved", f"QR code saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save the QR code:\n{e}")


# --- Standalone Test ---
# This allows you to run and test this widget by itself.
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Metadata Panel Standalone Test")
    layout = QVBoxLayout(window)
    
    # Create an instance of the new metadata manager panel
    metadata_panel = MetadataManagerPanel()
    layout.addWidget(metadata_panel)
    
    # Example of how the main app would get the data
    def test_get_data():
        data = metadata_panel.get_active_metadata()
        print("Active metadata:", data)
        QMessageBox.information(window, "Active Data", f"The current active metadata is:\n\n{json.dumps(data, indent=2)}")

    test_button = QPushButton("Test: Get Active Metadata")
    test_button.clicked.connect(test_get_data)
    layout.addWidget(test_button)
    
    window.resize(450, 600)
    window.show()
    sys.exit(app.exec())