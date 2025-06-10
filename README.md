# ImageImporter
 A lightweight image import utility built with Python and PyQt6, designed for photographers working with SD cards and digital cameras. This is a cross-platform tool aimed at making image ingesting cleaner, faster, and metadata-aware from day one.

### 🧩 Problem Statement

As a working photographer using vintage glass and manual lenses, my images lack embedded metadata for lens make, model, focal length, and aperture. Existing solutions treat metadata tagging as an afterthought — clunky add-ons to existing workflows, not built into the import process.

I need a tool where **metadata management is a core part of ingest**, not an extra step later. This includes custom lens profiles, selective tagging, and backup-aware import — with an emphasis on **workflow reliability and business resilience** from day one.

---

---

## ✅ Current Features

- Detect and select source folder (camera/SD card).
- Select destination folder(s), including an optional backup location.
- Choose how images are organized: by import date or by shot date (file mtime).
- Progress bar shows import status with live count and percentage.
- Screening question for whether custom metadata will be applied — logic stub in place.

---

## 🧠 Coming Soon

- Right-hand metadata panel that appears if "Yes" is selected for metadata tagging.
  - Global lens presets (Make, Model, Serial).
  - Checkbox-controlled fields for focal length, aperture, and notes.
- EXIFTool integration via subprocess, with user-defined presets.
- Persistent config files (to store preferred folders, lens data, etc.).
- Log file for each import session.
- Dry run option / import preview before committing.
- Drag-and-drop support (stretch goal).

---

## 🛠️ Requirements

- Python 3.10+
- PyQt6  
  Install via:  
  ```bash
  pip install PyQt6