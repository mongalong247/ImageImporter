**ImageImporter – User Guide**

📖 Purpose

ImageImporter is a simple but powerful image ingestion tool designed for photographers who want to:

Import images from a card, folder, or selected files.
Automatically organize files by shot date or import date.
Optionally create a backup copy to a second location.
Apply custom lens and shooting metadata on import.
Automatically identify lenses in-batch using printed ArUco markers.
Save presets for quick recall of commonly used metadata.

The goal is to make the import process faster, consistent, and repeatable — while reducing manual steps and human error. This is especially useful for photographers working with manual or vintage lenses that have no electronic contacts, meaning the camera can't record lens make, focal length, or aperture on its own.

🚀 Getting Started

1. Select Source Files

On launch, you can either:
Select Files – choose specific images for import.
Select Folder – point to a folder or memory card to import all images.

2. Choose Destination and Backup

Destination Folder – where your imported images will be stored.
Backup Folder (Optional) – a secondary copy will be created here if selected.

You can tick Open destination folder after import to have it open automatically when the import finishes.

Existing files at the destination are never silently overwritten — ImageImporter checks for conflicts and warns you before anything is replaced.

3. Organize Your Imports

Use the Organize by dropdown to choose between:

Import Date – groups files by the date/time of import.
Shot Date – uses the actual capture date from EXIF metadata.

Use the Folder Date Format input to customize how subfolders are named. Common formats are stored in a dropdown but this uses Python's strftime format codes, so any valid format string will work.

4. Apply Metadata (Optional)

There are two independent toggles in the Metadata panel — you can use either one on its own, or both together:

**Apply Custom Metadata**
Enable this to open the Metadata panel and apply lens/shooting data manually or via a saved preset.

Lens Presets Tab – first tab shown by default. Manage and recall saved lens presets here.
On first launch, this will be blank — build presets from the Active Metadata tab.

Active Metadata Tab – enter lens and shooting data manually:
Lens Make / Model
Focal Length
Aperture
Lens Serial
Notes

You can save this information as a preset to recall later for faster imports. Presets can also be exported to a file and imported on another machine (or shared with another user) — if an imported preset conflicts with one you already have, you'll be prompted to resolve it before anything is overwritten.

**Autodetect Scanned ArUco Tags**
If you shoot with manual/vintage lenses, you can print an ArUco marker for each lens and photograph it at the start of a shooting batch (or any time you switch lenses). Enable this toggle and ImageImporter will:

Scan the batch for ArUco markers.
Automatically split the batch into segments at each marker, based on chronological file order.
Apply the correct preset to each segment based on which marker was detected.

Each marker is tied to a permanent ID that's assigned once and never reused, even if you later delete or rename the associated preset — so your marker prints stay valid indefinitely and batch segmentation stays reliable over time.

5. Start Import

Click Start Import and ImageImporter will:

Copy your images to the chosen destination.
Optionally create a backup copy.
Organize them into date-based subfolders.
Apply any custom metadata (manual, preset-based, or ArUco-detected).
Log the import so you have a persistent record of what was imported and when.
Show a confirmation message when done.

If an individual file fails during import (corrupt file, permissions issue, etc.), ImageImporter isolates the failure to that file and continues processing the rest of the batch rather than stopping the whole import. Any failures are noted in the import log so you can review and retry them.

📷 Panasonic RAW (.RW2) Support

ImageImporter correctly extracts the full-resolution embedded JPEG preview from Panasonic .RW2 files (rather than falling back to a low-res thumbnail), so previews and quick-look images generated during import are accurately sized.

💡 Tips for Best Results

Choose Shot Date when importing from mixed sessions to maintain chronological order.
Build a preset library for your commonly used lenses and focal lengths — it saves time and is consistent.
If you shoot manual/vintage glass regularly, print a set of ArUco marker cards (one per lens) and keep them in your bag — photograph the marker at the start of each lens change and let autodetection handle the rest.
Export your preset library periodically as a backup, or to bring your presets to a new machine.
Use a clear folder structure to keep imports consistent over time.
Enable Open destination folder after import to quickly verify imports before ejecting a card.