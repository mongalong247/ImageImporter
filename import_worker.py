import os
import shutil
from PyQt6.QtCore import QObject, pyqtSignal
from utils import format_date

class ImportWorker(QObject):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_folder, dest_folder, backup_folder=None, organize_by="Import Date"):
        super().__init__()
        self.source_folder = source_folder
        self.dest_folder = dest_folder
        self.backup_folder = backup_folder
        self.organize_by = organize_by

    def run(self):
        files = [f for f in os.listdir(self.source_folder) if os.path.isfile(os.path.join(self.source_folder, f))]
        total = len(files)
        if total == 0:
            self.status.emit("No files to import.")
            self.finished.emit()
            return

        for i, file in enumerate(files):
            src = os.path.join(self.source_folder, file)

            try:
                timestamp = os.path.getmtime(src) if self.organize_by == "Shot Date" else os.path.getctime(src)
                date_str = format_date(timestamp)

                dest_subfolder = os.path.join(self.dest_folder, date_str)
                os.makedirs(dest_subfolder, exist_ok=True)
                dest = os.path.join(dest_subfolder, file)
                shutil.copy2(src, dest)

                if self.backup_folder:
                    backup_subfolder = os.path.join(self.backup_folder, date_str)
                    os.makedirs(backup_subfolder, exist_ok=True)
                    shutil.copy2(src, os.path.join(backup_subfolder, file))

                pct = int((i + 1) / total * 100)
                self.progress.emit(pct)
                self.status.emit(f"Imported {i+1}/{total}: {file}")
            except Exception as e:
                self.status.emit(f"Error importing {file}: {str(e)}")

        self.finished.emit()
