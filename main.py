import sys
from PyQt6.QtWidgets import QApplication
from update_checker import check_exiftool_update
from ui import ImageImporter

if __name__ == "__main__":
    check_exiftool_update("12.70")  # Replace with your bundled version

    app = QApplication(sys.argv)
    importer = ImageImporter()
    importer.show()
    sys.exit(app.exec())
