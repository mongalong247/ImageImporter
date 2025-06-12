import sys
from PyQt6.QtWidgets import QApplication
from ui import ImageImporter
from exiftool_manager import check_or_install_exiftool

if not check_or_install_exiftool():
    print("ExifTool could not be installed or updated. Exiting.")
    exit(1)

from ui import ImageImporter  # Import UI after dependencies are validated

if __name__ == "__main__":

    app = QApplication(sys.argv)
    importer = ImageImporter()
    importer.show()
    sys.exit(app.exec())
