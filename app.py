import sys
import os
import shutil
import json
import platform
import subprocess
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QComboBox, QHBoxLayout,
    QProgressBar, QCheckBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, QApplication, QMessageBox,
    QDialog, QScrollArea
)
# New: Import QIcon for setting the application icon
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QObject, Signal, QThread, QSettings

# --- Modular Imports ---
import exiftool_manager
import aruco_scan
import aruco_codes
from metadata_panel import MetadataManagerPanel

# --- CONSTANTS ---
APP_VERSION = "1.1.0"
NORMAL_STYLE = "color: gray; font-style: italic;"
ERROR_STYLE = "color: #d32f2f; font-weight: bold;"
WARNING_STYLE = "color: #b26a00; font-weight: bold;"
OK_STYLE = "color: #2e7d32;"

# Single shared list of recognized image/RAW extensions, used everywhere a
# file needs to be checked or filtered instead of three separately
# duplicated (and inconsistent) lists.
IMAGE_EXTENSIONS = (
    '.jpg', '.jpeg', '.png', '.heic', '.heif', '.tif', '.tiff',
    '.cr2', '.cr3', '.nef', '.arw', '.dng', '.rw2',
    '.orf', '.raf', '.pef', '.srw', '.rwl', '.3fr', '.raw',
)
IMAGE_FILE_DIALOG_FILTER = "Images (" + " ".join(f"*{ext}" for ext in IMAGE_EXTENSIONS) + ")"

# --- UTILITY FUNCTIONS ---

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def truncate_path(path: str, max_len: int = 60) -> str:
    # ... (function is unchanged)
    return path if len(path) <= max_len else f"...{path[-(max_len - 3):]}"

def open_folder(path):
    """Opens a folder in the default file explorer in a platform-agnostic way."""
    command = []
    if platform.system() == "Windows":
        command = ["explorer", os.path.normpath(path)]
    elif platform.system() == "Darwin": # macOS
        command = ["open", path]
    else: # Linux and other UNIX-like systems
        command = ["xdg-open", path]
    
    # --- Platform-specific configuration for subprocess to hide console window ---
    subprocess_args = {}
    if platform.system() == "Windows":
        subprocess_args['creationflags'] = subprocess.CREATE_NO_WINDOW
        
    try:
        if platform.system() == "Windows":
            # explorer.exe's exit code is notoriously unreliable -- it can
            # return non-zero even after successfully opening the folder --
            # so a non-zero result here isn't treated as a real failure.
            # macOS's 'open' and Linux's 'xdg-open' have meaningful exit
            # codes, so check=True still applies to those.
            subprocess.run(command, **subprocess_args)
        else:
            subprocess.run(command, check=True, **subprocess_args)
    except Exception as e:
        print(f"Failed to open folder {path}: {e}")

# --- BACKGROUND WORKER ---
class ImportWorker(QObject):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal()

    def __init__(self, source_folder, source_files, dest_folder, backup_folder, structure, date_format,
                 metadata, apply_metadata=False, autodetect_aruco=False, move_slate_frames=False, all_presets=None):
        super().__init__()
        self.source_folder = source_folder
        self.source_files = source_files
        self.dest_folder = dest_folder
        self.backup_folder = backup_folder
        self.structure = structure
        self.date_format = date_format
        self.metadata = metadata  # the Active Metadata tab's fields, used as the base preset when apply_metadata is on
        self.apply_metadata = apply_metadata  # "Apply custom metadata" checkbox -- the old, tag-independent behavior
        self.autodetect_aruco = autodetect_aruco  # "Autodetect scanned ArUco tags" checkbox -- independent of the above
        self.move_slate_frames = move_slate_frames
        self.all_presets = all_presets or {}  # full presets library (name -> fields incl. ArucoId), for ID lookup
        self.is_running = True
        self.log_lines = []   # full timestamped log of this run, for optional saving
        self.had_issues = False  # True if any file failed or a warning occurred

    def _log(self, message: str):
        """Records a timestamped line to the in-memory log and updates the status label."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_lines.append(f"[{timestamp}] {message}")
        self.status.emit(message)

    def stop(self):
        self.is_running = False

    @staticmethod
    def _get_unique_dest_path(dest_path: str) -> str:
        """
        If dest_path doesn't exist, returns it unchanged. Otherwise returns a
        sibling path with a numeric suffix (e.g. 'IMG_0001 (1).jpg') that
        doesn't collide with anything already on disk. Never overwrites an
        existing file silently.
        """
        if not os.path.exists(dest_path):
            return dest_path
        base, ext = os.path.splitext(dest_path)
        counter = 1
        while True:
            candidate = f"{base} ({counter}){ext}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    def _build_preset_segments(self, ordered_paths, base_preset):
        """
        Scans files -- already in chronological (capture-time) order -- for
        lens-preset ArUco tags, and builds a per-file metadata map: every
        file gets whichever preset was most recently matched before it, or
        base_preset if no tag has appeared yet in the batch.

        Unlike the QR approach this replaced, an ArUco tag only carries a
        small integer ID -- the actual lens data lives locally, in
        self.all_presets, keyed by each preset's own ArucoId. That means a
        detected ID with no matching local preset is a real, distinct
        failure mode (someone else's tag, a preset that was since deleted,
        a stale local presets file) and gets its own explicit log line
        rather than being silently treated the same as "no tag found".

        base_preset is the Active Metadata tab's fields when "Apply custom
        metadata" is also on, or an empty dict when it's off -- i.e. in
        autodetect-only mode, files before the first detected tag simply
        get no metadata, rather than falling back to whatever's sitting in
        the Active Metadata tab regardless of whether that checkbox is
        checked.

        Returns (preset_map, slate_frame_paths) where preset_map maps
        file_path -> metadata dict to apply, and slate_frame_paths lists
        every file that was itself detected as a tag frame (not yet acted
        on -- that's the "move slate frames" step).
        """
        id_to_preset = {}
        id_to_name = {}
        for name, data in self.all_presets.items():
            aruco_id = data.get("ArucoId")
            if aruco_id:
                id_to_preset[aruco_id] = {field: data.get(field, "") for field in aruco_codes.PRESET_FIELDS}
                id_to_name[aruco_id] = name

        preset_map = {}
        slate_frame_paths = []
        active_preset = base_preset

        for file_path in ordered_paths:
            if not self.is_running:
                break

            filename = os.path.basename(file_path)

            try:
                frame, frame_info = aruco_scan.get_scannable_frame_with_info(file_path)
            except Exception as e:
                frame, frame_info = None, f"extraction error: {e}"
                self._log(f"Warning: Could not extract a scannable image from {filename}: {e}")

            if frame is None:
                self._log(f"No scannable image available for {filename} ({frame_info}) -- treated as no tag.")
                preset_map[file_path] = active_preset
                continue

            try:
                aruco_id = aruco_scan.decode_aruco_id(frame)
            except Exception as e:
                aruco_id = None
                self._log(f"Warning: ArUco decode failed for {filename}: {e}")

            if aruco_id is not None:
                matched_preset = id_to_preset.get(aruco_id)
                if matched_preset is not None:
                    active_preset = matched_preset
                    slate_frame_paths.append(file_path)
                    self._log(
                        f"Detected ArUco tag #{aruco_id:03d} in {filename} ({frame_info}) "
                        f"-- switching to preset '{id_to_name[aruco_id]}'."
                    )
                else:
                    self.had_issues = True
                    self._log(
                        f"Warning: ArUco tag #{aruco_id:03d} detected in {filename} ({frame_info}), "
                        "but no local preset has that ID -- check for a stale presets file or a "
                        "tag printed on a different machine."
                    )
            else:
                self._log(f"No ArUco tag found in {filename} ({frame_info}).")

            preset_map[file_path] = active_preset

        return preset_map, slate_frame_paths

    def run(self):
        try:
            image_paths = self.source_files or [
                os.path.join(self.source_folder, f)
                for f in os.listdir(self.source_folder)
                if f.lower().endswith(IMAGE_EXTENSIONS)
            ]
            total_files = len(image_paths)
            if total_files == 0:
                self._log("No compatible image files found to import.")
                self.finished.emit()
                return

            self._log(f"Starting import of {total_files} file(s)...")

            # Computed once up front and reused both for chronological
            # ordering/ArUco segmentation below and for shot-date subfolder
            # naming in the main loop, instead of asking ExifTool for the
            # same file's date twice.
            shot_dates = {file_path: exiftool_manager.get_shot_date(file_path) for file_path in image_paths}

            ordered_paths = image_paths
            preset_map = {}
            slate_frame_paths = []

            if self.autodetect_aruco:
                # Tag cut points only make sense in capture-time order, not
                # filesystem/selection order, so re-sort chronologically.
                # Files with no readable date sort last, in their original
                # relative order.
                original_index = {p: i for i, p in enumerate(image_paths)}
                ordered_paths = sorted(
                    image_paths,
                    key=lambda p: (shot_dates[p] is None, shot_dates[p] or datetime.max, original_index[p])
                )
                # In autodetect-only mode (apply_metadata off), files before the
                # first detected tag get nothing, rather than falling
                # back to whatever's sitting in the Active Metadata tab
                # regardless of whether that checkbox is actually checked.
                base_preset = self.metadata if self.apply_metadata else {}
                preset_map, slate_frame_paths = self._build_preset_segments(ordered_paths, base_preset)
            elif self.apply_metadata:
                # Old, tag-independent behavior: one preset, blanket-applied
                # to the whole batch, in whatever order files were given.
                preset_map = {p: self.metadata for p in image_paths}

            slate_frame_path_set = set(slate_frame_paths)
            succeeded = 0
            failed = 0
            renamed = 0

            for idx, file_path in enumerate(ordered_paths):
                if not self.is_running:
                    self._log("Import cancelled by user.")
                    break

                filename = os.path.basename(file_path)
                try:
                    shot_date = shot_dates.get(file_path)
                    if self.structure == "Shot Date":
                        subfolder_name = shot_date.strftime(self.date_format) if shot_date else "unknown_date"
                    else:
                        subfolder_name = datetime.now().strftime(self.date_format)

                    is_slate_frame = file_path in slate_frame_path_set
                    if self.move_slate_frames and is_slate_frame:
                        effective_subfolder = os.path.join(subfolder_name, "slates")
                    else:
                        effective_subfolder = subfolder_name

                    dest_path_with_subfolder = os.path.join(self.dest_folder, effective_subfolder)
                    os.makedirs(dest_path_with_subfolder, exist_ok=True)
                    dest_file_path = os.path.join(dest_path_with_subfolder, filename)

                    final_dest_path = self._get_unique_dest_path(dest_file_path)
                    if final_dest_path != dest_file_path:
                        renamed += 1
                        self._log(
                            f"'{filename}' already exists at destination -- "
                            f"saving as '{os.path.basename(final_dest_path)}' instead of overwriting."
                        )

                    self._log(f"Copying {filename}...")
                    shutil.copy2(file_path, final_dest_path)

                    if self.backup_folder:
                        backup_path_with_subfolder = os.path.join(self.backup_folder, effective_subfolder)
                        os.makedirs(backup_path_with_subfolder, exist_ok=True)
                        backup_file_path = self._get_unique_dest_path(
                            os.path.join(backup_path_with_subfolder, filename)
                        )
                        shutil.copy2(file_path, backup_file_path)

                    if self.apply_metadata or self.autodetect_aruco:
                        active_metadata = preset_map.get(file_path, self.metadata if self.apply_metadata else {})
                        applied_fields = {k: v for k, v in active_metadata.items() if v}
                        if applied_fields:
                            self._log(
                                f"Applying metadata to {filename}: "
                                + ", ".join(f"{k}={v}" for k, v in applied_fields.items())
                            )
                            if not exiftool_manager.write_metadata(final_dest_path, active_metadata):
                                self.had_issues = True
                                self._log(f"Warning: Metadata write failed for {filename}")
                        elif self.apply_metadata:
                            # Apply custom metadata is on, so every file is expected to get at
                            # least the base preset -- an empty result here means the Active
                            # Metadata tab itself has nothing in it, which is a misconfiguration
                            # worth flagging rather than a normal outcome.
                            self.had_issues = True
                            self._log(f"Warning: No metadata fields to write for {filename} -- the active preset is empty.")
                        else:
                            # Autodetect-only mode (apply_metadata off): no ArUco tag has been
                            # seen yet for this file, so having nothing to write is expected.
                            self._log(f"No ArUco lens preset active yet for {filename} -- nothing written.")

                    succeeded += 1
                except Exception as e:
                    # A problem with one file (locked, corrupted, permissions,
                    # disk full for that write, etc.) must not abort the rest
                    # of the batch -- log it and keep going.
                    failed += 1
                    self.had_issues = True
                    self._log(f"Error importing '{filename}': {e} -- skipping and continuing.")

                self.progress.emit(int((idx + 1) / total_files * 100))

            if self.is_running:
                summary = f"Import complete. {succeeded} of {total_files} file(s) copied successfully."
                if renamed:
                    summary += f" {renamed} renamed to avoid overwriting existing files."
                if slate_frame_paths:
                    if self.move_slate_frames:
                        summary += f" {len(slate_frame_paths)} ArUco lens-slate frame(s) detected and moved into 'slates' subfolders."
                    else:
                        summary += f" {len(slate_frame_paths)} ArUco lens-slate frame(s) detected."
                elif self.autodetect_aruco:
                    # Silent zero-detection is exactly the failure mode that's easy to miss --
                    # say it plainly, and treat it as worth a second look rather than burying
                    # it as just another line in a "successful" run.
                    self.had_issues = True
                    summary += " 0 ArUco lens-slate frames detected -- no tag-based metadata was applied."
                if failed:
                    summary += f" {failed} failed -- see status messages above for details."
                self._log(summary)
        except Exception as e:
            self.had_issues = True
            self._log(f"Import process failed: {e}")
        finally:
            self.finished.emit()

class LogViewerDialog(QDialog):
    """
    Shows the full log from an import run in a scrollable, read-only text
    box, with the option to save it. Available after every run (not just
    ones with errors) so behavior can be inspected even when nothing threw
    an exception -- e.g. confirming whether a ArUco tag was actually
    detected, and exactly which metadata fields were applied to which file.
    """
    def __init__(self, log_lines, parent=None):
        super().__init__(parent)
        self.log_lines = log_lines
        self.setWindowTitle("Import Log")
        self.setMinimumSize(420, 360)
        self.setMaximumSize(1000, 1000)
        self.resize(700, 600)

        layout = QVBoxLayout(self)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        text_edit.setFontFamily("Courier New")
        text_edit.setPlainText("\n".join(log_lines))
        layout.addWidget(text_edit)

        button_layout = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        save_button = QPushButton("Save As...")
        save_button.clicked.connect(self._on_save)
        button_layout.addStretch(1)
        button_layout.addWidget(close_button)
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)

    def _on_save(self):
        default_name = f"import_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Import Log", default_name, "Text Files (*.txt)")
        if not file_path:
            return
        try:
            with open(file_path, 'w') as f:
                f.write("\n".join(self.log_lines))
            QMessageBox.information(self, "Saved", f"Log saved to:\n{file_path}")
        except IOError as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save the log file:\n{e}")


# --- GUI: MAIN WINDOW ---
class ImageImporter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photo Import & Tagger")
        self.setGeometry(100, 100, 900, 600)
        self.setMinimumSize(700, 500)

        # New: Set the window icon using the resource path helper
        self.setWindowIcon(QIcon(resource_path("assets/app_icon.ico")))

        self.settings = QSettings("PhotoTagger", "ImageImporter")

        # The content here has grown over time (log viewer, ArUco status, etc.)
        # and will likely keep growing. Rather than the window's minimum
        # size creeping up with it and eventually exceeding a laptop's
        # screen height (as happened before this fix), everything lives
        # inside a scroll area: the window itself stays a sane, fixed
        # minimum size, and content that doesn't fit scrolls instead of
        # forcing the OS to fight over window geometry.
        container_widget = QWidget()
        self.layout = QHBoxLayout(container_widget)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container_widget)
        self.setCentralWidget(scroll_area)

        self.source_folder = ""
        self.selected_files = []
        self.dest_folder = ""
        self.backup_folder = ""
        self.import_thread = None
        self.import_worker = None
        self.exiftool_available = False
        self.metadata_panel = MetadataManagerPanel()
        self.build_import_form()
        self._create_menu_bar()
        self.layout.addWidget(self.import_form_group)
        self.layout.addWidget(self.metadata_panel)
        self.metadata_panel.setVisible(False)
        self.load_settings()
        self._refresh_exiftool_status()

    def build_import_form(self):
        # (This function is unchanged)
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
        self.metadata_toggle.setToolTip(
            "Applies the Active Metadata tab's fields to every imported file. "
            "Independent of ArUco autodetection below -- use either, both, or neither."
        )
        self.metadata_toggle.toggled.connect(self.metadata_panel.setVisible)
        self.aruco_autodetect_checkbox = QCheckBox("Autodetect scanned ArUco tags")
        self.aruco_autodetect_checkbox.setToolTip(
            "Scans each file for a lens-preset ArUco tag and tags files from that point "
            "onward with the matching preset (looked up locally by the tag's ID). If 'Apply "
            "custom metadata' is also checked, the Active Metadata tab is used as the starting "
            "preset before the first tag is found; otherwise, files before the first detected "
            "tag get no metadata written."
        )
        self.open_dest_checkbox = QCheckBox("Open destination folder after import")
        self.open_dest_checkbox.setToolTip("If checked, the primary destination folder will open automatically when the import finishes.")
        self.move_slates_checkbox = QCheckBox("Move detected slate frames into a 'slates' subfolder")
        self.move_slates_checkbox.setToolTip(
            "If checked, any frame where a lens-preset ArUco tag was detected is filed into a "
            "'slates' subfolder (inside each date folder) instead of alongside your regular photos. "
            "Off by default -- slate frames are imported like any other photo unless you enable this."
        )
        self.import_button = QPushButton("Start Import")
        self.import_button.setStyleSheet("font-weight: bold; padding: 8px;")
        self.import_button.clicked.connect(self.start_import)
        self.close_button = QPushButton("Close Application")
        self.close_button.setStyleSheet("padding: 8px;")
        self.close_button.clicked.connect(self.close)
        self.close_button.setVisible(False)
        self.view_log_button = QPushButton("View Import Log...")
        self.view_log_button.clicked.connect(self._on_view_log)
        self.view_log_button.setVisible(False)
        self.last_import_log = []
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
        self.import_layout.addWidget(self.aruco_autodetect_checkbox)
        self.exiftool_status_label = QLabel("ExifTool: checking...")
        self.exiftool_status_label.setWordWrap(True)
        self.exiftool_status_label.setStyleSheet(NORMAL_STYLE)
        self.import_layout.addWidget(self.exiftool_status_label)
        self.import_layout.addWidget(self.open_dest_checkbox)
        self.import_layout.addWidget(self.move_slates_checkbox)
        self.import_layout.addStretch()
        self.import_layout.addWidget(self.import_button)
        self.import_layout.addWidget(self.view_log_button)
        self.import_layout.addWidget(self.close_button)
        self.import_layout.addWidget(self.status_label)
        self.import_layout.addWidget(self.progress)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        settings_menu = menu_bar.addMenu("&Settings")
        exiftool_path_action = QAction("Set &ExifTool Path...", self)
        exiftool_path_action.triggered.connect(self._on_set_exiftool_path)
        settings_menu.addAction(exiftool_path_action)
        clear_exiftool_path_action = QAction("&Clear Custom ExifTool Path", self)
        clear_exiftool_path_action.triggered.connect(self._on_clear_exiftool_path)
        settings_menu.addAction(clear_exiftool_path_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _show_about_dialog(self):
        # (This function is unchanged)
        QMessageBox.about(self, "About Photo Import & Tagger", f"<b>Photo Import & Tagger</b><p>Version: {APP_VERSION}</p><p>A utility for importing photos with reliable backups and powerful, preset-driven metadata tagging.</p><p>This tool helps photographers using manual lenses to embed critical EXIF data directly into their workflow.</p>")

    # --- ExifTool status & configuration ---

    def _on_set_exiftool_path(self):
        """Lets the user point at an existing ExifTool install (system or bundled elsewhere)."""
        exe_filter = "exiftool.exe (exiftool.exe)" if platform.system() == "Windows" else "exiftool (exiftool)"
        path, _ = QFileDialog.getOpenFileName(self, "Select ExifTool Executable", "", exe_filter + ";;All Files (*)")
        if not path:
            return
        exiftool_manager.set_custom_path(path)
        self._refresh_exiftool_status()

    def _on_clear_exiftool_path(self):
        """Clears any custom ExifTool path, reverting to the auto-detect chain."""
        exiftool_manager.set_custom_path("")
        self._refresh_exiftool_status()
        QMessageBox.information(self, "ExifTool Path Cleared",
                                 "Custom path cleared. The app will auto-detect ExifTool again.")

    def _refresh_exiftool_status(self):
        """Re-runs ExifTool resolution and updates the status banner + dependent UI."""
        success, message = exiftool_manager.ensure_exiftool_available()
        self.exiftool_available = success
        self.exiftool_status_label.setText(("ExifTool: " if success else "ExifTool unavailable: ") + message)
        self.exiftool_status_label.setStyleSheet(OK_STYLE if success else WARNING_STYLE)
        # Metadata tagging (and ArUco scanning of RAW files, which relies on ExifTool to pull
        # each file's embedded preview) can't work without ExifTool -- reflect that in both
        # toggles, but don't fight the user if they re-enable it after fixing the path.
        self.metadata_toggle.setEnabled(success)
        self.aruco_autodetect_checkbox.setEnabled(success)
        if not success:
            self.metadata_toggle.setChecked(False)
            self.aruco_autodetect_checkbox.setChecked(False)

    # ... (All other class methods like select_source_files, start_import, load_settings, etc. remain unchanged)
    def select_source_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Image Files", self.source_folder, IMAGE_FILE_DIALOG_FILTER)
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
        if not self._validate_paths(): return
        try:
            file_count = len(self.selected_files) if self.selected_files else len([f for f in os.listdir(self.source_folder) if f.lower().endswith(IMAGE_EXTENSIONS)])
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
        current_metadata = self.metadata_panel.get_active_metadata()
        self.import_worker = ImportWorker(
            source_folder=self.source_folder, source_files=self.selected_files, dest_folder=self.dest_folder,
            backup_folder=self.backup_folder, structure=self.structure_dropdown.currentText(), date_format=python_format,
            metadata=current_metadata, apply_metadata=self.metadata_toggle.isChecked(),
            autodetect_aruco=self.aruco_autodetect_checkbox.isChecked(), move_slate_frames=self.move_slates_checkbox.isChecked(),
            all_presets=self.metadata_panel.presets)
        self.import_thread = QThread()
        self.import_worker.moveToThread(self.import_thread)
        self.import_thread.started.connect(self.import_worker.run)
        self.import_worker.progress.connect(self.progress.setValue)
        self.import_worker.status.connect(self.status_label.setText)
        self.import_worker.finished.connect(self.on_import_finished)
        self.import_thread.start()
    def on_import_finished(self):
        # Capture what we need from the worker before we let go of it below.
        had_issues = bool(self.import_worker and self.import_worker.had_issues)
        log_lines = list(self.import_worker.log_lines) if self.import_worker else []
        self.last_import_log = log_lines  # kept for on-demand viewing, whether or not anything went wrong

        if self.import_thread:
            self.import_thread.quit()
            self.import_thread.wait()
        self.import_thread = None
        self.import_worker = None
        self.close_button.setVisible(True)
        self.import_button.setVisible(True)
        self.view_log_button.setVisible(True)
        self.status_label.setText("Import complete. Ready to close or start another import.")
        if self.open_dest_checkbox.isChecked():
            if self.dest_folder and os.path.isdir(self.dest_folder):
                try:
                    open_folder(self.dest_folder)
                except Exception as e:
                    self.status_label.setText(f"Import complete, but failed to open folder: {e}")
        if had_issues:
            self._offer_save_log(log_lines)

    def _on_view_log(self):
        """Opens the full log from the most recent import, whether or not it had issues."""
        if not self.last_import_log:
            QMessageBox.information(self, "No Log Available", "There's no import log to show yet.")
            return
        dialog = LogViewerDialog(self.last_import_log, self)
        dialog.exec()

    def _offer_save_log(self, log_lines):
        """
        Prompts the user after a run that hit at least one error or warning:
        save the full log to a file they choose, or discard it entirely.
        Nothing is written to disk unless they explicitly choose to save.
        """
        reply = QMessageBox.question(
            self, "Import Completed With Errors",
            "There was an error during the import. Would you like to save the log file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return  # Purge: log_lines is simply discarded, nothing is written.

        default_name = f"import_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Import Log", default_name, "Text Files (*.txt)")
        if not file_path:
            return  # User backed out of the save dialog -- log is still discarded.

        try:
            with open(file_path, 'w') as f:
                f.write("\n".join(log_lines))
            QMessageBox.information(self, "Log Saved", f"Log saved to:\n{file_path}")
        except IOError as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save the log file:\n{e}")

    def load_settings(self):
        self.date_format_combo.setCurrentText(self.settings.value("dateFormat", "YYYY-MM-DD"))
        self.open_dest_checkbox.setChecked(self.settings.value("openDestAfterImport", False, type=bool))
        self.move_slates_checkbox.setChecked(self.settings.value("moveSlateFramesToSubfolder", False, type=bool))
        self.aruco_autodetect_checkbox.setChecked(self.settings.value("autodetectArucoTags", False, type=bool))
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
        self.settings.setValue("dateFormat", self.date_format_combo.currentText())
        self.settings.setValue("openDestAfterImport", self.open_dest_checkbox.isChecked())
        self.settings.setValue("moveSlateFramesToSubfolder", self.move_slates_checkbox.isChecked())
        self.settings.setValue("autodetectArucoTags", self.aruco_autodetect_checkbox.isChecked())
        self.settings.setValue("lastSourcePath", self.source_folder)
        self.settings.setValue("lastDestPath", self.dest_folder)
        self.settings.setValue("lastBackupPath", self.backup_folder)
    def closeEvent(self, event):
        self.save_settings()
        if self.import_worker: self.import_worker.stop()
        if self.import_thread:
            self.import_thread.quit()
            self.import_thread.wait()
        event.accept()

# --- APPLICATION ENTRY POINT ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # ExifTool availability is no longer treated as fatal: the app launches
    # either way, and ImageImporter._refresh_exiftool_status() (called from
    # its __init__) reflects the real status in the UI and disables the
    # metadata-tagging feature specifically if nothing usable was found.
    # Importing photos without metadata tagging still works fine.
    importer = ImageImporter()
    if not importer.exiftool_available:
        QMessageBox.warning(
            importer, "ExifTool Not Found",
            "ExifTool could not be found or installed automatically, so metadata "
            "tagging is disabled for this session.\n\n"
            "Photo importing will still work normally. To enable tagging, install "
            "ExifTool and either add it to your system PATH, or point the app at it "
            "directly via Settings > Set ExifTool Path..."
        )
    importer.show()
    sys.exit(app.exec())
