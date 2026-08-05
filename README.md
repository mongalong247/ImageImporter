# ImageImporter

A one-click photo import tool for photographers that:
- Organizes images by shot date or import date
- Adds optional custom metadata (lens, focal length, notes)
- Allows creation and loading of lens metadata presets
- Automatically bundles and updates ExifTool
- Works offline with a clean, beginner-friendly interface

## Current Features
- ✅ Import all images from selected folder
- ✅ Select individual files (not just folders)
- ✅ Organize into folders by import or shot date
- ✅ Add metadata to EXIF via ExifTool
- ✅ Create, load, and delete lens metadata presets
- ✅ Automatically download and manage ExifTool on first run
- ✅ Modern PySide6-based GUI
- ✅ Windows support
- ✅ Mac/Linux prompt for exiftool
- ✅ Export/import of lens preset config

## Development Progress
- App scaffolding/UI: 100%
- ExifTool integration: 100%
- Metadata writing: 100%
- Presets system: 100%
- Cross-platform support: 75%
- Final packaging: 100%

## Building & releasing

Portable builds for Windows, macOS, and Linux are produced by
`.github/workflows/release.yml` — push a version tag (`v1.4.0`) and it
builds all three natively and attaches them as a draft GitHub Release.
See [`packaging/README.md`](packaging/README.md) for the full process,
including how to build locally on a single platform.
