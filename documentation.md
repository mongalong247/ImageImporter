**ImageImporter – User Guide**

📖 Purpose

ImageImporter is a simple but powerful image ingestion tool designed for photographers who want to:

Import images from a card, folder, or selected files.
Automatically organize files by shot date or import date.
Optionally create a backup copy to a second location.
Apply custom lens and shooting metadata on import.
Save presets for quick recall of commonly used metadata.

The goal is to make the import process faster, consistent, and repeatable — while reducing manual steps and human error.

🚀 Getting Started

1. Select Source Files

On launch, you can either:
Select Files – choose specific images for import.
Select Folder – point to a folder or memory card to import all images.

2. Choose Destination and Backup

Destination Folder – where your imported images will be stored.
Backup Folder (Optional) – a secondary copy will be created here if selected.

You can tick Open destination folder after import to have it open automatically when the import finishes.

3. Organize Your Imports

Use the Organize by dropdown to choose between:

Import Date – groups files by the date/time of import.
Shot Date – uses the actual capture date from EXIF metadata.

Use the Folder Date Format input to customize how subfolders are named.  Common formats are stored in a dropdown but this uses Python’s strftime format codes, so any valid format string will work.

4. Apply Metadata (Optional)

Enable Apply Custom Metadata to open the Metadata panel.
Lens Presets Tab – first tab shown by default.  This allows the user to manage and recall saved lens presets.

On first launch, this will be blank — build presets from the Active Metadata tab.

Active Metadata Tab – enter lens and shooting data manually:

Lens Make / Model
Focal Length
Aperture
Lens Serial
Notes

You can save this information as a preset to recall later for faster imports.

5. Start Import

Click Start Import and ImageImporter will:

Copy your images to the chosen destination.
Optionally create a backup copy.
Organize them into date-based subfolders.
Apply any custom metadata.
Show a confirmation message when done.

💡 Tips for Best Results

Choose Shot Date when importing from mixed sessions to maintain chronological order.
Build a preset library for your commonly used lenses and focal lengths — it saves time and is consistent.

Use a clear folder structure to keep imports consistent over time.
Enable Open destination folder after import to quickly verify imports before ejecting a card.
