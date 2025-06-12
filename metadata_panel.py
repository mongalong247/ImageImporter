from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QLineEdit, QTextEdit, QCheckBox

class MetadataPanel(QGroupBox):
    def __init__(self):
        super().__init__("Metadata Entry")
        self.layout = QGridLayout(self)

        self.make_input = QLineEdit()
        self.model_input = QLineEdit()
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

        self.layout.addWidget(QLabel("Lens Make:"), 0, 0)
        self.layout.addWidget(self.make_input, 0, 1)
        self.layout.addWidget(QLabel("Lens Model:"), 1, 0)
        self.layout.addWidget(self.model_input, 1, 1)

        self.layout.addWidget(self.focal_checkbox, 2, 0)
        self.layout.addWidget(self.focal_input, 2, 1)
        self.layout.addWidget(self.aperture_checkbox, 3, 0)
        self.layout.addWidget(self.aperture_input, 3, 1)
        self.layout.addWidget(self.serial_checkbox, 4, 0)
        self.layout.addWidget(self.serial_input, 4, 1)
        self.layout.addWidget(self.notes_checkbox, 5, 0)
        self.layout.addWidget(self.notes_input, 5, 1, 2, 1)

        self.focal_checkbox.stateChanged.connect(lambda: self.focal_input.setEnabled(self.focal_checkbox.isChecked()))
        self.aperture_checkbox.stateChanged.connect(lambda: self.aperture_input.setEnabled(self.aperture_checkbox.isChecked()))
        self.serial_checkbox.stateChanged.connect(lambda: self.serial_input.setEnabled(self.serial_checkbox.isChecked()))
        self.notes_checkbox.stateChanged.connect(lambda: self.notes_input.setEnabled(self.notes_checkbox.isChecked()))

    def get_metadata(self) -> dict:
        return {
            "LensMake": self.make_input.text(),
            "LensModel": self.model_input.text(),
            "FocalLength": self.focal_input.text() if self.focal_checkbox.isChecked() else None,
            "FNumber": self.aperture_input.text() if self.aperture_checkbox.isChecked() else None,
            "LensSerialNumber": self.serial_input.text() if self.serial_checkbox.isChecked() else None,
            "ImageDescription": self.notes_input.toPlainText() if self.notes_checkbox.isChecked() else None
        }
