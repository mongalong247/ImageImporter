from PyQt6.QtCore import QObject, pyqtSignal
import os
import shutil
from datetime import datetime
from exif_manager import get_exif_data, get_shot_date
import exiftool

class ImportWorker(QObject):
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

    def run(self):
        try:
            if self.source_files:
                image_paths = self.source_files
            else:
                image_paths = [
                    os.path.join(self.source_folder, f)
                    for f in os.listdir(self.source_folder)
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.cr2', '.nef', '.arw', '.dng'))
                ]

            total_files = len(image_paths)
            if total_files == 0:
                self.status.emit("No images found.")
                self.finished.emit()
                return

            self.status.emit(f"Found {total_files} image(s). Starting import...")

            for idx, file_path in enumerate(image_paths):
                try:
                    # Determine destination subfolder based on selected structure
                    if self.structure == "Shot Date":
                        shot_date = get_shot_date(file_path)
                        subfolder_name = shot_date.strftime("%Y-%m-%d") if shot_date else "unknown_date"
                    else:  # Import Date
                        subfolder_name = datetime.now().strftime("%Y-%m-%d")

                    dest_path = os.path.join(self.dest_folder, subfolder_name)
                    os.makedirs(dest_path, exist_ok=True)

                    filename = os.path.basename(file_path)
                    dest_file_path = os.path.join(dest_path, filename)
                    shutil.copy2(file_path, dest_file_path)

                    if self.backup_folder:
                        backup_path = os.path.join(self.backup_folder, subfolder_name)
                        os.makedirs(backup_path, exist_ok=True)
                        shutil.copy2(file_path, os.path.join(backup_path, filename))

                    if self.metadata:
                        self.apply_metadata(dest_file_path)

                except Exception as e:
                    self.status.emit(f"Error with {file_path}: {e}")

                progress_percent = int((idx + 1) / total_files * 100)
                self.progress.emit(progress_percent)

            self.status.emit("Import complete.")
        except Exception as e:
            self.status.emit(f"Import failed: {e}")
        finally:
            self.finished.emit()

    def apply_metadata(self, file_path):
        try:
            with exiftool.ExifTool() as et:
                args = []
                if self.metadata.get("lens_make"):
                    args.append(f"-EXIF:LensMake={self.metadata['lens_make']}")
                if self.metadata.get("lens_model"):
                    args.append(f"-EXIF:LensModel={self.metadata['lens_model']}")
                if self.metadata.get("focal_length"):
                    args.append(f"-EXIF:FocalLength={self.metadata['focal_length']}")
                if self.metadata.get("aperture"):
                    args.append(f"-EXIF:FNumber={self.metadata['aperture']}")
                if self.metadata.get("lens_serial"):
                    args.append(f"-EXIF:LensSerialNumber={self.metadata['lens_serial']}")
                if self.metadata.get("notes"):
                    args.append(f"-XMP:Description={self.metadata['notes']}")

                if args:
                    et.execute(*args, file_path)
        except Exception as e:
            self.status.emit(f"Metadata error: {e}")
