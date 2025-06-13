# ImageImporter

A cross-platform image ingestion tool built for photographers using vintage or manual lenses, with baked-in metadata tagging, clean backups, and import automation.

---

## ✅ Features (Current MVP)

- Import from selected images or full SD card folder
- Organize into folders by:
  - Import Date
  - Shot Date (via EXIF metadata)
- PyQt-based graphical interface
- Threaded import (prevents UI freezing)
- Progress bar and import stats
- Built-in **Metadata Tagging Panel**:
  - Lens Make / Model
  - Optional fields: Focal Length, Aperture, Serial Number, Notes
- **ExifTool Integration (Windows)**:
  - Automatically downloads latest version
  - Verifies version on launch
  - Includes required `perl5.dll` and support folder
  - Metadata writing tested and functional

---

## 🛠 How to Use

1. Clone/download the repo
2. Create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # or source venv/bin/activate (Mac/Linux)```
   
3. Install dependencies:
```pip install -r requirements.txt```

4.Run the application:
```python app.py```


🚧 Roadmap

Add per-image metadata overrides

Cross-platform ExifTool integration (macOS, Linux)

Save/load metadata presets (lens setups)

Export logs and error reports

Final build packaging for distribution


📝 Known Issues

    None — metadata and ExifTool logic now functioning correctly on Windows.

🎯 Next Steps

    Modular cleanup & directory structure review

    Add unit tests and formal logging

    Prepare for cross-platform compatibility

    Build a proper GUI toggle for dry run/test modes