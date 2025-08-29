import sys
import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox, QHBoxLayout,
    QLineEdit, QTextEdit, QGroupBox, QGridLayout, QApplication, QMessageBox,
    QTabWidget
)

# Define the path for the presets file, relative to this script's location.
# This assumes it will live alongside the main app.py, which has a 'resources' subfolder.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(APP_DIR, "resources")
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
        
        layout.addWidget(load_group)
        layout.addWidget(save_group)
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
